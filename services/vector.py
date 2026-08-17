"""Service vectoriel — Indexation et recherche par similarité sémantique (embeddings).

Refacto DevOps / SOLID / Thread-Safe :
- Injection de dépendance stricte (plus de fallback vers controllers.context).
- Thread-safety garantie : tous les accès à _data sont protégés par _lock.
- Gestion robuste des fichiers corrompus (backup automatique + alerte).
- Plus d'exposition de _data (encapsulation respectée).
- Index secondaire pour déduplication O(1) au lieu de O(N).
- MT 7.4 : Rétropropagation de score sur les chunks (update_score + élagage toxique).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import numpy as np
import orjson

from config.constants import (
    BAD_COUNT_PRUNING_THRESHOLD,
    CONSOLIDATE_DEDUP_SIMILARITY,
    CONSOLIDATE_GRACE_HOURS,
    CONSOLIDATE_MAX_ITER,
    CONSOLIDATE_PRUNE_WEIGHT,
    MAX_VECTOR_DOCS,
    MEMORY_DIR,
    SCORE_PRUNING_THRESHOLD,
    WEIGHT_MAX,
    WEIGHT_MIN,
)
from ports import VectorPort
from services.vector_cache import VECTOR_CACHE_TTL_SECONDS, MatrixCache, VectorCache
from services.vector_dimension import (
    MIGRATION_OK,
    MIGRATION_REINDEXED,
    MIGRATION_RESET,
    DimensionManager,
)
from services.vector_docs import build_message_doc
from services.vector_embedder import Embedder
from services.vector_index import VectorIndex
from services.vector_search import build_normalized_matrix, rank_matrix
from services.vector_stats import cache_hit_rate, conversation_weights, estimate_dedup, weight_stats
from services.vector_weighting import WeightConsolidator

_logger = logging.getLogger("jarvis.vector")

# Fichier de persistance de l'index vectoriel (documents + embeddings)
VECTOR_PATH = os.path.join(MEMORY_DIR, "vector_index.json")
VECTOR_BACKUP_PATH = os.path.join(MEMORY_DIR, "vector_index.backup.json")
EXPECTED_DIM = 768
EXPECTED_MODEL = "hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M"

# Ré-export pour compatibilité ascendante (constants propres au cache)
__all__ = [
    "VECTOR_CACHE_TTL_SECONDS",
    "VectorService",
    "EXPECTED_DIM",
    "EXPECTED_MODEL",
    "MIGRATION_OK",
    "MIGRATION_REINDEXED",
    "MIGRATION_RESET",
]


def _archive_corrupted_file(path: str) -> str:
    """Archiver un fichier corrompu par renommage (pas de copie = pas de boucle de retry).

    Returns the path of the archived file, or empty string on failure.
    """
    corrupted_path = f"{path}.corrupted.{int(time.time())}"
    try:
        if os.path.exists(path):
            os.rename(path, corrupted_path)
            _logger.critical("Fichier corrompu archivé : %s", corrupted_path)
            return corrupted_path
    except OSError as rename_error:
        _logger.error("Échec de l'archivage du fichier corrompu : %s", rename_error)
    return ""


class VectorService(VectorPort):
    """Index vectoriel local : orchestre indexation, embedding et recherche cosinus.

    Thread-safe et résilient : toutes les mutations d'état sont protégées par un verrou,
    et les fichiers corrompus sont automatiquement sauvegardés avant réinitialisation.
    """

    def __init__(self, inference_service: Any) -> None:
        """Initialise l'index vectoriel.

        Args:
            inference_service: Service d'inférence pour le calcul d'embeddings
                (obligatoire — DI stricte : VectorService ne doit pas créer
                sa propre InferenceService, ce qui créerait un second
                AdapterRegistry/pool HTTP indépendant).
        """
        os.makedirs(os.path.dirname(VECTOR_PATH), exist_ok=True)

        self._lock = threading.RLock()
        self._inference = inference_service
        self._embedder = Embedder(inference_service)
        self._cache = VectorCache()
        self._matrix_cache = MatrixCache()

        # Chargement sécurisé des données
        self._data = self._load_secure()
        self._index = VectorIndex(self._data, VECTOR_PATH, self._lock)

        # Index secondaire pour déduplication O(1) des messages de conversation
        self._message_index = self._build_message_index()

        # Migration de dimension
        self.last_migration = self._ensure_dimension()

        # Flag "mutations en attente d'écriture" (flush groupé, 14.0)
        self._dirty = False

    # ==============================================================================
    # GESTION SÉCURISÉE DES DONNÉES (Thread-Safe + Résilience)
    # ==============================================================================

    def _build_message_index(self) -> dict[tuple[str, str], bool]:
        """Construit un index secondaire pour les messages de conversation (O(1) lookup)."""
        index = {}
        for doc in self._data.get("documents", []):
            metadata = doc.get("metadata", {})
            if metadata.get("source") == "conversation":
                conv_id = metadata.get("conv_id")
                msg_id = metadata.get("msg_id")
                if conv_id and msg_id:
                    index[(conv_id, msg_id)] = True
        return index

    def _load_secure(self) -> dict[str, Any]:
        """Charge les données avec gestion robuste des fichiers corrompus."""
        if not os.path.exists(VECTOR_PATH):
            return {"documents": [], "embedding_dim": None}

        try:
            with open(VECTOR_PATH, "rb") as f:
                data = orjson.loads(f.read())

            if isinstance(data, dict) and "documents" in data:
                _logger.info("Index vectoriel chargé avec succès (%d documents)", len(data["documents"]))
                return data
            else:
                raise ValueError("Structure de données invalide")

        except (orjson.JSONDecodeError, OSError, ValueError):
            # Archivage du fichier corrompu par renommage (pas de copie = pas de boucle de retry)
            _archive_corrupted_file(VECTOR_PATH)

            # Retourne un état vide mais valide
            return {"documents": [], "embedding_dim": None}

    def _save_secure(self) -> None:
        """Sauvegarde les données de manière atomique (évite la corruption)."""
        temp_path = VECTOR_PATH + ".tmp"
        try:
            with open(temp_path, "wb") as f:
                f.write(orjson.dumps(self._data))
            # Renommage atomique (évite la corruption en cas de crash pendant l'écriture)
            os.replace(temp_path, VECTOR_PATH)
        except OSError as e:
            _logger.error("Échec de la sauvegarde de l'index vectoriel : %s", e)
            # Nettoyage du fichier temporaire en cas d'échec
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError as cleanup_err:
                _logger.debug("Échec du nettoyage du fichier temporaire %s: %s", temp_path, cleanup_err)
            raise

    def flush(self) -> None:
        """Écrit l'index sur disque si des mutations sont en attente (flush groupé).

        Appelé en fin de lot (vectorisation) et à l'arrêt propre du service.
        Écriture unique pour N mutations : `_dirty` est reset après l'écriture.
        """
        with self._lock:
            if not self._dirty:
                return
            self._save_secure()
            self._dirty = False

    # ==============================================================================
    # MIGRATION DE DIMENSION
    # ==============================================================================

    def _resolve_expected_dim(self) -> int:
        """Dimension d'embedding attendue (injectable pour les tests)."""
        return EXPECTED_DIM

    def _ensure_dimension(self) -> str:
        """Vérifie et migre la dimension des embeddings si nécessaire."""
        mgr = DimensionManager(self._data)
        return mgr.ensure_dimension(self._resolve_expected_dim(), EXPECTED_MODEL)

    # ==============================================================================
    # EMBEDDING (Thread-Safe)
    # ==============================================================================

    def _embed(self, text: str) -> list[float]:
        """Calcule l'embedding d'un texte (thread-safe)."""
        # Pas de mutation d'état ici : Embedder est stateless
        return self._embedder.embed(text)

    def preload(self) -> None:
        """Précharge la connexion au backend d'embedding (appelé au warmup)."""
        try:
            self._embed("warmup")
            _logger.info("Backend d'embedding préchargé avec succès")
        except Exception as e:
            _logger.warning("Preload embedding échoué : %s", e)

    # ==============================================================================
    # INDEXATION (Thread-Safe + O(1) Dedup)
    # ==============================================================================

    def _now(self) -> float:
        """Horodatage courant (injectable pour les tests)."""
        return time.time()

    def index(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Ajoute un document à l'index (sans l'embedder immédiatement)."""
        with self._lock:
            if self._index.add_document(text, metadata):
                self._save_secure()
                self._clear_search_cache()

    def index_batch(self, documents: list[tuple[str, dict[str, Any] | None]]) -> None:
        """Ajoute plusieurs documents en une seule opération (atomique, dedup)."""
        added = False
        with self._lock:
            for text, metadata in documents:
                if self._index.add_document(text, metadata):
                    added = True
            if added:
                self._save_secure()
        if added:
            self._clear_search_cache()

    def _embed_pending(self) -> int:
        """Calcule les embeddings pour tous les documents en attente par lots (thread-safe).

        Utilise embed_batch de l'adaptateur pour réduire les appels HTTP (ROADMAP 14.5).
        Taille de lot : 32 textes par appel.
        Mise à jour incrémentale de la matrice normalisée (17.2).
        """
        count = 0
        batch_size = 32
        with self._lock:
            # Collecter les documents sans embedding
            pending = [(idx, doc) for idx, doc in enumerate(self._data["documents"]) if doc.get("embedding") is None]

            # Traiter par lots
            newly_embedded_docs = []
            newly_embedded_embeddings = []
            for i in range(0, len(pending), batch_size):
                batch = pending[i : i + batch_size]
                texts = [doc["text"] for _, doc in batch]
                try:
                    embeddings = self._inference.embed_batch(texts)
                    for (idx, doc), emb in zip(batch, embeddings):
                        norm_emb = self._normalize_embedding(emb)
                        doc["embedding"] = norm_emb
                        newly_embedded_docs.append(doc)
                        newly_embedded_embeddings.append(np.asarray(norm_emb, dtype=np.float32))
                        count += 1
                except Exception as e:
                    _logger.error("Échec embedding batch : %s", e)

            if count:
                self._dirty = True
                # Mise à jour incrémentale de la matrice au lieu de clear_cache()
                if newly_embedded_docs:
                    new_embeddings_matrix = np.vstack(newly_embedded_embeddings)
                    self._append_to_matrix_cache(newly_embedded_docs, new_embeddings_matrix)
            # 14.0 : une seule écriture pour tout le lot vectorisé.
            self.flush()
        return count

    @staticmethod
    def _normalize_embedding(embedding: list[float]) -> list[float]:
        """Normalise L2 un embedding (16.1 : normalisation faite à l'indexation)."""
        vec = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm == 0:
            return embedding
        return list((vec / norm).tolist())

    def vectorize_pending(self) -> int:
        """Calcule les embeddings pour tous les documents en attente."""
        return self._embed_pending()

    # ==============================================================================
    # INDEXATION DES MESSAGES (O(1) Dedup avec index secondaire)
    # ==============================================================================

    def index_message(
        self, conv_id: str, msg_id: str, role: str, content: str, ts: float, extra: dict[str, Any] | None = None
    ) -> None:
        """Indexe un message (dedup O(1) via index secondaire)."""
        if not content or not content.strip():
            return

        with self._lock:
            # Vérification O(1) au lieu de O(N)
            if (conv_id, msg_id) in self._message_index:
                return  # Déjà indexé

            # Ajout du document
            doc = build_message_doc(conv_id, msg_id, role, content, ts, extra)
            self._data["documents"].append(doc)

            # Mise à jour de l'index secondaire
            self._message_index[(conv_id, msg_id)] = True

            # 14.0 : flush groupé — pas d'écriture par message, on marque dirty.
            self._dirty = True
            self._clear_search_cache()

    def ingest_message(self, conv_id: str, msg_id: str, role: str, content: str, ts: float) -> None:
        """Indexe un message et calcule son embedding (auto-ingest)."""
        self.index_message(conv_id, msg_id, role, content, ts)
        self.vectorize_pending()

    # ==============================================================================
    # PONDÉRATION, SCORE ET CONSOLIDATION (Thread-Safe)
    # ==============================================================================

    def adjust_weight(self, conv_id: str, msg_id: str, delta: float, conversations: Any | None = None) -> int:
        """Ajuste le poids d'un souvenir (feedback), clampe et ajuste le précédent."""
        with self._lock:
            wc = WeightConsolidator(self._data["documents"])
            count = wc.apply_weight(conv_id, msg_id, delta, WEIGHT_MIN, WEIGHT_MAX)

            prev_id = wc.preceding_user_msg_id(conversations, conv_id, msg_id)
            if prev_id and delta:
                count += wc.apply_weight(conv_id, prev_id, delta * 0.5, WEIGHT_MIN, WEIGHT_MAX)

            if count:
                self._save_secure()
                self._clear_search_cache()

            return count

    def update_score(self, chunk_id: str, delta: float) -> int:
        """Met à jour le score et le bad_count d'un chunk spécifique (MT 7.4).

        Retourne le nombre de chunks mis à jour (0 ou 1).
        """
        count = 0
        with self._lock:
            for doc in self._data["documents"]:
                metadata = doc.get("metadata", {})
                if metadata.get("chunk_id") == chunk_id:
                    current_score = float(metadata.get("score", 0.0))
                    current_bad_count = int(metadata.get("bad_count", 0))

                    metadata["score"] = current_score + delta
                    if delta < 0:
                        metadata["bad_count"] = current_bad_count + 1

                    count += 1

            if count > 0:
                self._save_secure()
                self._clear_search_cache()

        return count

    def consolidate(self) -> None:
        """Consolidation hors ligne : dedup + prune + élagage des chunks toxiques (thread-safe)."""
        with self._lock:
            docs = self._data["documents"]

            # MT 7.4 : Initialiser les métadonnées manquantes (backward compat)
            for d in docs:
                metadata = d.get("metadata", {})
                metadata.setdefault("score", 0.0)
                metadata.setdefault("bad_count", 0)

            wc = WeightConsolidator(docs)

            to_remove = wc.dedup(CONSOLIDATE_DEDUP_SIMILARITY, CONSOLIDATE_MAX_ITER)
            kept = wc.prune(CONSOLIDATE_PRUNE_WEIGHT, CONSOLIDATE_GRACE_HOURS, self._now())

            # MT 7.4 : élagage des chunks toxiques
            toxic_indices = set()
            for idx, d in enumerate(docs):
                if idx in to_remove or d not in kept:
                    continue

                metadata = d.get("metadata", {})
                score = float(metadata.get("score", 0.0))
                bad_count = int(metadata.get("bad_count", 0))

                if bad_count > BAD_COUNT_PRUNING_THRESHOLD or score < SCORE_PRUNING_THRESHOLD:
                    toxic_indices.add(idx)

            kept_docs = [
                d for idx, d in enumerate(docs) if idx not in to_remove and d in kept and idx not in toxic_indices
            ]

            # Limitation de la taille de l'index
            if len(kept_docs) > MAX_VECTOR_DOCS:
                kept_docs.sort(
                    key=lambda d: (
                        d.get("metadata", {}).get("weight", 0.0),
                        d.get("metadata", {}).get("created_at", 0.0),
                    ),
                    reverse=True,
                )
                kept_docs = kept_docs[:MAX_VECTOR_DOCS]

            self._data["documents"] = kept_docs
            self._data["last_consolidation"] = time.time()
            self._data.setdefault("consolidation_runs", 0)
            self._data["consolidation_runs"] += 1

            self._save_secure()

            # Reconstruction de l'index secondaire
            self._message_index = self._build_message_index()

        self.clear_cache()

    # ==============================================================================
    # RECHERCHE VECTORIELLE (Thread-Safe + Cache)
    # ==============================================================================

    def clear_cache(self) -> None:
        """Vide le cache de recherche (résultats + matrice normalisée)."""
        self._cache.clear()
        self._matrix_cache.clear()

    def _clear_search_cache(self) -> None:
        """Vide uniquement le cache de résultats de recherche (garde la matrice normalisée).

        Utilisé pour les mutations qui ne changent pas les embeddings (poids, scores, nouveaux docs sans embedding).
        """
        self._cache.clear()

    def _append_to_matrix_cache(self, new_docs: list[dict[str, Any]], new_embeddings: np.ndarray) -> None:
        """Ajoute de nouveaux embeddings normalisés à la matrice existante (vstack incrémental)."""
        self._matrix_cache.append(new_docs, new_embeddings)

    def _get_matrix(self, query_dim: int) -> tuple[list[dict[str, Any]], np.ndarray | None]:
        """Retourne (valid_docs, matrice normalisée) en réutilisant le cache."""
        cached = self._matrix_cache.get()
        if cached is not None:
            return cached
        valid_docs, matrix = build_normalized_matrix(self._data["documents"], query_dim)
        self._matrix_cache.set((valid_docs, matrix))
        return self._matrix_cache.get()  # type: ignore[return-value]  # garanti par set() ci-dessus

    def search(
        self,
        query: str,
        top_k: int = 5,
        agent: str | None = None,
        sim_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Recherche sémantique avec cache et scoring pondéré.

        Utilise une recherche bornée avec relance plafonnée (max 3 tentatives) :
        1. Tentative 1 : borne min(len(docs), max(top_k*5, 50))
        2. Si résultats filtrés < top_k : tentative 2, borne ×2
        3. Si toujours < top_k : tentative finale non bornée + warning

        Args:
            agent: Restreint aux documents dont ``metadata.agent`` vaut
                exactement cette valeur (ex: "@cyber"). ``None`` = tous.
            sim_threshold: Seuil de similarité cosinus appliqué par
                ``rank_matrix`` : les résultats sous le seuil sont exclus.
        """
        if not query or not self._data.get("documents"):
            return []

        # Le cache n'est fiable que pour la recherche non filtrée (clé query+top_k)
        cacheable = agent is None and sim_threshold == 0.5
        now = self._now()
        if cacheable:
            cached = self._cache.get(query, top_k, now)
            if cached is not None:
                return cached

        # Calcul de l'embedding de la requête
        try:
            query_vec = np.array(self._embed(query), dtype=np.float32)
        except Exception as e:
            _logger.error("Échec calcul embedding requête : %s", e)
            return []

        return self._run_bounded_search(
            query, query_vec, top_k, now, agent=agent, sim_threshold=sim_threshold, cacheable=cacheable
        )

    def _run_bounded_search(
        self,
        query: str,
        query_vec: np.ndarray,
        top_k: int,
        now: float,
        agent: str | None = None,
        sim_threshold: float = 0.5,
        cacheable: bool = True,
    ) -> list[dict[str, Any]]:
        """Exécute la boucle de recherche bornée avec relance plafonnée (max 3 tentatives)."""
        with self._lock:
            docs = self._data["documents"]
            max_docs = len(docs)
            valid_docs, matrix = self._get_matrix(len(query_vec))

            # Filtrage par agent avant scoring (matrice et documents alignés)
            if agent is not None and matrix is not None:
                keep = [doc.get("metadata", {}).get("agent") == agent for doc in valid_docs]
                valid_docs = [doc for doc, ok in zip(valid_docs, keep) if ok]
                matrix = matrix[keep]

            # Borne initiale : min(len(docs), max(top_k*5, 50))
            bound = min(max_docs, max(top_k * 5, 50))

            results: list[dict[str, Any]] = []
            attempts = 0
            max_attempts = 3

            while attempts < max_attempts:
                attempts += 1

                all_results = rank_matrix(query_vec, valid_docs, matrix, top_k=bound, sim_threshold=sim_threshold)

                # Filtrage aval : scoring et ranking (pondération + troncature top_k)
                results = WeightConsolidator(docs).score_and_rank(all_results, top_k, now)

                # Si on a assez de résultats après filtrage, on s'arrête
                if len(results) >= top_k:
                    break

                # Sinon, on élargit la borne pour la tentative suivante
                if attempts < max_attempts - 1:
                    # Tentative 2 : borne ×2
                    bound = min(max_docs, bound * 2)
                else:
                    # Tentative finale (3) : non bornée
                    bound = max_docs
                    _logger.warning(
                        "Recherche vectorielle : relance non bornée déclenchée (top_k=%d, "
                        "résultats après filtre=%d). Filtre potentiellement mal calibré.",
                        top_k,
                        len(results),
                    )

        # Mise en cache (uniquement pour les recherches non filtrées)
        if cacheable:
            self._cache.put(query, top_k, results, now)
        return results

    # ==============================================================================
    # STATISTIQUES ET OBSERVABILITÉ (Thread-Safe)
    # ==============================================================================

    @property
    def _cache_hits(self) -> int:
        return self._cache.hits

    @property
    def _cache_misses(self) -> int:
        return self._cache.misses

    def stats(self) -> dict[str, Any]:
        """Statistiques de l'index (thread-safe)."""
        with self._lock:
            docs = self._data.get("documents", [])
            total = len(docs)
            embedded = sum(1 for d in docs if d.get("embedding") is not None)
            conv_weights = conversation_weights(docs)
            dedup_estimated = estimate_dedup(docs)

        wm, lw = weight_stats(conv_weights)
        hit_rate = cache_hit_rate(self._cache_hits, self._cache_misses)

        return {
            "total": total,
            "embedded": embedded,
            "pending": total - embedded,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": hit_rate,
            "embedding_backend": "ollama",
            "embedding_model": EXPECTED_MODEL,
            "embedding_dim": EXPECTED_DIM,
            "stored_dim": self._data.get("embedding_dim"),
            "migration_status": self.last_migration,
            "using_fallback": False,  # Embedder refactoré n'a plus de fallback
            "weight_mean": wm,
            "low_weight_ratio": lw,
            "conversation_docs": len(conv_weights),
            "message_indexed": len(conv_weights),
            "dedup_estimated": dedup_estimated,
            "last_consolidation": self._data.get("last_consolidation"),
            "consolidation_runs": self._data.get("consolidation_runs", 0),
        }

    def is_healthy(self) -> bool:
        """Vérifie que l'index est valide et lisible."""
        if not os.path.exists(VECTOR_PATH):
            return True  # Pas encore créé = sain

        try:
            with open(VECTOR_PATH, "rb") as f:
                data = orjson.loads(f.read())
            return isinstance(data, dict) and "documents" in data
        except (orjson.JSONDecodeError, OSError):
            return False
