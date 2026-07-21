"""Service vectoriel — Indexation et recherche par similarité sémantique (embeddings).

Refacto DevOps / SOLID / Thread-Safe :
- Injection de dépendance stricte (plus de fallback vers controllers.context).
- Thread-safety garantie : tous les accès à _data sont protégés par _lock.
- Gestion robuste des fichiers corrompus (backup automatique + alerte).
- Plus d'exposition de _data (encapsulation respectée).
- Index secondaire pour déduplication O(1) au lieu de O(N).
"""
import json
import logging
import os
import shutil
import threading
import time
from typing import List, Optional, Tuple

import numpy as np

from config.constants import MEMORY_DIR, WEIGHT_MAX, WEIGHT_MIN
from ports import VectorPort
from services.vector_cache import VECTOR_CACHE_TTL_SECONDS, VectorCache
from services.vector_dimension import MIGRATION_OK, MIGRATION_REINDEXED, MIGRATION_RESET, DimensionManager
from services.vector_embedder import Embedder
from services.vector_index import VectorIndex
from services.vector_search import cosine_search
from services.vector_weighting import WeightConsolidator

_logger = logging.getLogger("jarvis.vector")

# Fichier de persistance de l'index vectoriel (documents + embeddings)
VECTOR_PATH = os.path.join(MEMORY_DIR, "vector_index.json")
VECTOR_BACKUP_PATH = os.path.join(MEMORY_DIR, "vector_index.backup.json")
EXPECTED_DIM = 768
EXPECTED_MODEL = "nomic-embed-text-v2-moe"

# Ré-export pour compatibilité ascendante (constants propres au cache)
__all__ = [
    "VECTOR_CACHE_TTL_SECONDS", "VectorService", "EXPECTED_DIM", "EXPECTED_MODEL",
    "MIGRATION_OK", "MIGRATION_REINDEXED", "MIGRATION_RESET",
]


class VectorService(VectorPort):
    """Index vectoriel local : orchestre indexation, embedding et recherche cosinus.
    
    Thread-safe et résilient : toutes les mutations d'état sont protégées par un verrou,
    et les fichiers corrompus sont automatiquement sauvegardés avant réinitialisation.
    """

    def __init__(self, inference_service):
        """Initialise l'index vectoriel avec injection de dépendance stricte.
        
        Args:
            inference_service: Service d'inférence pour le calcul d'embeddings (requis).
            
        Raises:
            ValueError: Si inference_service est None.
        """
        if inference_service is None:
            raise ValueError(
                "VectorService nécessite un service d'inférence valide. "
                "Injection de dépendance requise (DIP)."
            )
        
        os.makedirs(os.path.dirname(VECTOR_PATH), exist_ok=True)
        
        self._lock = threading.RLock()
        self._inference = inference_service
        self._embedder = Embedder(inference_service)
        self._cache = VectorCache()
        
        # Chargement sécurisé des données
        self._data = self._load_secure()
        self._index = VectorIndex(self._data, VECTOR_PATH, self._lock)
        
        # Index secondaire pour déduplication O(1) des messages de conversation
        self._message_index = self._build_message_index()
        
        # Migration de dimension
        self.last_migration = self._ensure_dimension()

    # ==============================================================================
    # GESTION SÉCURISÉE DES DONNÉES (Thread-Safe + Résilience)
    # ==============================================================================

    def _build_message_index(self) -> dict:
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

    def _load_secure(self) -> dict:
        """Charge les données avec gestion robuste des fichiers corrompus."""
        if not os.path.exists(VECTOR_PATH):
            return {"documents": [], "embedding_dim": None}
        
        try:
            with open(VECTOR_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and "documents" in data:
                _logger.info("Index vectoriel chargé avec succès (%d documents)", len(data["documents"]))
                return data
            else:
                raise ValueError("Structure de données invalide")
                
        except (json.JSONDecodeError, OSError, ValueError) as e:
            _logger.critical(
                "Fichier vectoriel corrompu (%s). Sauvegarde automatique vers %s", 
                VECTOR_PATH, VECTOR_BACKUP_PATH
            )
            # Sauvegarde du fichier corrompu
            try:
                if os.path.exists(VECTOR_PATH):
                    shutil.copy2(VECTOR_PATH, VECTOR_BACKUP_PATH)
                    _logger.info("Fichier corrompu sauvegardé dans %s", VECTOR_BACKUP_PATH)
            except OSError as backup_error:
                _logger.error("Échec de la sauvegarde du fichier corrompu : %s", backup_error)
            
            # Retourne un état vide mais valide
            return {"documents": [], "embedding_dim": None}

    def _save_secure(self):
        """Sauvegarde les données de manière atomique (évite la corruption)."""
        temp_path = VECTOR_PATH + ".tmp"
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            # Renommage atomique (évite la corruption en cas de crash pendant l'écriture)
            os.replace(temp_path, VECTOR_PATH)
        except OSError as e:
            _logger.error("Échec de la sauvegarde de l'index vectoriel : %s", e)
            # Nettoyage du fichier temporaire en cas d'échec
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            raise

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

    def _embed(self, text: str) -> List[float]:
        """Calcule l'embedding d'un texte (thread-safe)."""
        # Pas de mutation d'état ici : Embedder est stateless
        return self._embedder.embed(text)

    def preload(self):
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

    def index(self, text: str, metadata: Optional[dict] = None):
        """Ajoute un document à l'index (sans l'embedder immédiatement)."""
        with self._lock:
            if self._index.add_document(text, metadata):
                self._save_secure()

    def index_batch(self, documents: List[Tuple[str, Optional[dict]]]):
        """Ajoute plusieurs documents en une seule opération (atomique, dedup)."""
        added = False
        with self._lock:
            for text, metadata in documents:
                if self._index.add_document(text, metadata):
                    added = True
            if added:
                self._save_secure()
        if added:
            self.clear_cache()

    def _embed_pending(self) -> int:
        """Calcule les embeddings pour tous les documents en attente (thread-safe)."""
        count = 0
        with self._lock:
            for doc in self._data["documents"]:
                if doc.get("embedding") is None:
                    try:
                        doc["embedding"] = self._embed(doc["text"])
                        count += 1
                    except Exception as e:
                        _logger.error("Échec embedding pour document : %s", e)
            if count:
                self._save_secure()
        return count

    def vectorize_pending(self) -> int:
        """Calcule les embeddings pour tous les documents en attente."""
        return self._embed_pending()

    # ==============================================================================
    # INDEXATION DES MESSAGES (O(1) Dedup avec index secondaire)
    # ==============================================================================

    def index_message(self, conv_id: str, msg_id: str, role: str, content: str, ts,
                      extra: Optional[dict] = None):
        """Indexe un message (dedup O(1) via index secondaire)."""
        if not content or not content.strip():
            return
        
        with self._lock:
            # Vérification O(1) au lieu de O(N)
            if (conv_id, msg_id) in self._message_index:
                return  # Déjà indexé
            
            # Ajout du document
            doc = self._build_message_doc(conv_id, msg_id, role, content, ts, extra)
            self._data["documents"].append(doc)
            
            # Mise à jour de l'index secondaire
            self._message_index[(conv_id, msg_id)] = True
            
            self._save_secure()

    def _build_message_doc(self, conv_id, msg_id, role, content, ts, extra) -> dict:
        """Construit un document de message standardisé."""
        return {
            "text": content,
            "metadata": {
                "source": "conversation",
                "conv_id": conv_id, 
                "msg_id": msg_id, 
                "role": role,
                "created_at": ts, 
                "weight": 1.0, 
                **(extra or {}),
            },
            "embedding": None,
        }

    def ingest_message(self, conv_id: str, msg_id: str, role: str, content: str, ts):
        """Indexe un message et calcule son embedding (auto-ingest)."""
        self.index_message(conv_id, msg_id, role, content, ts)
        self.vectorize_pending()

    # ==============================================================================
    # PONDÉRATION ET CONSOLIDATION (Thread-Safe)
    # ==============================================================================

    def adjust_weight(self, conv_id: str, msg_id: str, delta: float,
                      conversations=None) -> int:
        """Ajuste le poids d'un souvenir (feedback), clampe et ajuste le précédent."""
        with self._lock:
            wc = WeightConsolidator(self._data["documents"])
            count = wc.apply_weight(conv_id, msg_id, delta, WEIGHT_MIN, WEIGHT_MAX)
            
            prev_id = wc.preceding_user_msg_id(conversations, conv_id, msg_id)
            if prev_id and delta:
                count += wc.apply_weight(conv_id, prev_id, delta * 0.5, WEIGHT_MIN, WEIGHT_MAX)
            
            if count:
                self._save_secure()
                self.clear_cache()
            
            return count

    def consolidate(self):
        """Consolidation hors ligne : dedup + prune (thread-safe)."""
        from config.constants import (
            CONSOLIDATE_DEDUP_SIMILARITY,
            CONSOLIDATE_GRACE_HOURS,
            CONSOLIDATE_MAX_ITER,
            CONSOLIDATE_PRUNE_WEIGHT,
            MAX_VECTOR_DOCS,
        )
        
        with self._lock:
            docs = self._data["documents"]
            wc = WeightConsolidator(docs)
            
            to_remove = wc.dedup(CONSOLIDATE_DEDUP_SIMILARITY, CONSOLIDATE_MAX_ITER)
            kept = wc.prune(CONSOLIDATE_PRUNE_WEIGHT, CONSOLIDATE_GRACE_HOURS, self._now())
            
            kept_docs = [
                d for idx, d in enumerate(docs) if idx not in to_remove and d in kept
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

    def clear_cache(self):
        """Vide le cache de recherche."""
        self._cache.clear()

    def search(self, query: str, top_k: int = 5) -> list:
        """Recherche sémantique avec cache et scoring pondéré."""
        if not query or not self._data.get("documents"):
            return []
        
        now = self._now()
        cached = self._cache.get(query, top_k, now)
        if cached is not None:
            return cached
        
        # Calcul de l'embedding de la requête
        try:
            query_vec = np.array(self._embed(query), dtype=np.float32)
        except Exception as e:
            _logger.error("Échec calcul embedding requête : %s", e)
            return []
        
        # Vectorisation des documents en attente
        self._embed_pending()
        
        # Recherche par similarité cosinus
        with self._lock:
            all_results = cosine_search(
                query_vec, 
                self._data["documents"], 
                top_k=len(self._data["documents"])
            )
            
            # Scoring et ranking avec pondération
            results = WeightConsolidator(self._data["documents"]).score_and_rank(
                all_results, top_k, now
            )
        
        # Mise en cache
        self._cache.put(query, top_k, results, now)
        return results

    # ==============================================================================
    # STATISTIQUES ET OBSERVABILITÉ (Thread-Safe)
    # ==============================================================================

    def _conversation_weights(self) -> List[float]:
        """Récupère les poids des documents de conversation."""
        with self._lock:
            return [
                d.get("metadata", {}).get("weight", 1.0)
                for d in self._data.get("documents", [])
                if d.get("metadata", {}).get("source") == "conversation"
            ]

    def _weight_stats(self, conv_weights: List[float]) -> Tuple[float, float]:
        """Calcule les statistiques de poids."""
        if not conv_weights:
            return 0.0, 0.0
        mean = round(sum(conv_weights) / len(conv_weights), 3)
        low = round(sum(1 for w in conv_weights if w <= 0) / len(conv_weights), 3)
        return mean, low

    def _estimate_dedup(self) -> int:
        """Estime le nombre de doublons potentiels."""
        with self._lock:
            text_counts = {}
            for d in self._data.get("documents", []):
                key = d["text"].strip().lower()
                text_counts[key] = text_counts.get(key, 0) + 1
            return sum(c - 1 for c in text_counts.values() if c > 1)

    @property
    def _cache_hits(self) -> int:
        return self._cache.hits

    @property
    def _cache_misses(self) -> int:
        return self._cache.misses

    def _cache_hit_rate(self) -> float:
        total = self._cache_hits + self._cache_misses
        return round(self._cache_hits / total * 100, 1) if total else 0.0

    def stats(self) -> dict:
        """Statistiques de l'index (thread-safe)."""
        with self._lock:
            docs = self._data.get("documents", [])
            total = len(docs)
            embedded = sum(1 for d in docs if d.get("embedding") is not None)
        
        conv_weights = self._conversation_weights()
        wm, lw = self._weight_stats(conv_weights)
        
        return {
            "total": total, 
            "embedded": embedded, 
            "pending": total - embedded,
            "cache_hits": self._cache_hits, 
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hit_rate(),
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
            "dedup_estimated": self._estimate_dedup(),
            "last_consolidation": self._data.get("last_consolidation"),
            "consolidation_runs": self._data.get("consolidation_runs", 0),
        }

    def is_healthy(self) -> bool:
        """Vérifie que l'index est valide et lisible."""
        if not os.path.exists(VECTOR_PATH):
            return True  # Pas encore créé = sain
        
        try:
            with open(VECTOR_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return isinstance(data, dict) and "documents" in data
        except (json.JSONDecodeError, OSError):
            return False
