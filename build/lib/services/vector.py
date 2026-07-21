"""Service vectoriel — Indexation et recherche par similarité sémantique (embeddings).

Façade fine (SRP) : VectorService orchestre l'indexation et la recherche en
déléguant chaque responsabilité à un module spécialisé :
  * vector_index.VectorIndex       -> stockage, IO, dédup
  * vector_embedder.Embedder       -> calcul d'embedding (+ fallback)
  * vector_dimension.DimensionManager -> cohérence/migration de dimension
  * vector_weighting.WeightConsolidator -> poids, consolidation, ranking

Le contrat public (index, search, stats, adjust_weight, consolidate, ...) est
inchangé. L'attribut ``_data`` reste exposé (utilisé par les tests existants).
"""
import json
import logging
import os
import threading
import time

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
EXPECTED_DIM = 768
EXPECTED_MODEL = "nomic-embed-text-v2-moe"

# Ré-export pour compatibilité ascendante (constants propres au cache)
__all__ = [
    "VECTOR_CACHE_TTL_SECONDS", "VectorService", "EXPECTED_DIM", "EXPECTED_MODEL",
    "MIGRATION_OK", "MIGRATION_REINDEXED", "MIGRATION_RESET",
]



class VectorService(VectorPort):
    """Index vectoriel local : orchestre indexation, embedding et recherche cosinus.

    Délègue chaque responsabilité à un module spécialisé pour respecter le
    principe de responsabilité unique (SRP).
    """

    def __init__(self, inference=None):
        """Initialise l'index vectoriel : charge les données, prépare le cache LRU.

        `inference` (optionnel) est le backend d'embedding, injecté par l'appelant
        (DIP). À défaut, `_get_inference` retombe sur `controllers.context` pour
        compatibilité ascendante (tests et appelants existants sans injection).
        """
        os.makedirs(os.path.dirname(VECTOR_PATH), exist_ok=True)
        self._lock = threading.RLock()
        self._index = VectorIndex(self._load(), VECTOR_PATH, self._lock)
        self._data = self._index._data
        self._inference = inference
        self._embedder = Embedder(None)
        self._cache = VectorCache()
        self.last_migration = self._ensure_dimension()

    # --- Délégation : dimension/migration -----------------------------------

    def _resolve_expected_dim(self) -> int:
        """Dimension d'embedding attendue (injectable pour les tests)."""
        return EXPECTED_DIM

    def _ensure_dimension(self) -> str:
        mgr = DimensionManager(self._data)
        return mgr.ensure_dimension(self._resolve_expected_dim(), EXPECTED_MODEL)

    # --- Délégation : embedding ---------------------------------------------

    def _get_inference(self):
        if self._inference is not None:
            return self._inference
        try:
            from controllers.context import get_context
            ctx = get_context()
            _logger.info("Backend embedding : Ollama (%s)", EXPECTED_MODEL)
            return ctx.inference
        except Exception as e:
            _logger.warning("Embedding backend indisponible: %s", e)
            return None

    def _embed(self, text: str) -> list[float]:
        self._embedder = Embedder(self._get_inference())
        return self._embedder.embed(text)

    def preload(self):
        """Précharge la connexion au backend d'embedding (appelé au warmup)."""
        inference = self._get_inference()
        if inference:
            try:
                inference.embed("warmup")
            except Exception as e:
                _logger.warning("Preload embedding: %s", e)

    # --- Délégation : indexation/IO ------------------------------------------

    def _now(self) -> float:
        """Horodatage courant (injectable pour les tests)."""
        return time.time()

    @property
    def _using_fallback(self) -> bool:
        """Expose l'etat de repli histogramme (delegate vers Embedder)."""
        return self._embedder.using_fallback

    @staticmethod
    def _load() -> dict:
        try:
            with open(VECTOR_PATH) as f:
                data = json.load(f)
            if isinstance(data, dict) and "documents" in data:
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {"documents": [], "embedding_dim": None}

    def _save(self):
        self._index.save()

    def _exists(self, text: str) -> bool:
        return self._index.exists(text)

    def index(self, text: str, metadata: dict = None):
        """Ajoute un document à l'index (sans l'embedder immédiatement)."""
        if self._index.add_document(text, metadata):
            self._save()

    def index_batch(self, documents: list[tuple[str, dict | None]]):
        """Ajoute plusieurs documents en une seule opération (atomique, dedup)."""
        added = False
        with self._lock:
            for text, metadata in documents:
                if self._index.add_document(text, metadata):
                    added = True
            if added:
                self._save()
        if added:
            self.clear_cache()

    def _embed_pending(self) -> int:
        count = 0
        for doc in self._data["documents"]:
            if doc["embedding"] is None:
                doc["embedding"] = self._embed(doc["text"])
                count += 1
        if count:
            self._save()
        return count

    def vectorize_pending(self) -> int:
        """Calcule les embeddings pour tous les documents en attente."""
        return self._embed_pending()

    # --- Indexation messages -------------------------------------------------

    def index_message(self, conv_id: str, msg_id: str, role: str, content: str, ts,
                      extra: dict = None):
        """Indexe un message (dedup conv_id:msg_id, poids initial 1.0)."""
        if not content or not content.strip():
            return
        if self._exists_key(conv_id, msg_id):
            return
        self._data["documents"].append(self._build_message_doc(conv_id, msg_id, role, content, ts, extra))
        self._save()

    def _build_message_doc(self, conv_id, msg_id, role, content, ts, extra) -> dict:
        return {
            "text": content,
            "metadata": {
                "source": "conversation",
                "conv_id": conv_id, "msg_id": msg_id, "role": role,
                "created_at": ts, "weight": 1.0, **(extra or {}),
            },
            "embedding": None,
        }

    def _exists_key(self, conv_id: str, msg_id: str) -> bool:
        return any(
            d.get("metadata", {}).get("conv_id") == conv_id
            and d.get("metadata", {}).get("msg_id") == msg_id
            for d in self._data["documents"]
        )

    def ingest_message(self, conv_id: str, msg_id: str, role: str, content: str, ts):
        """Indexe un message et calcule son embedding (auto-ingest)."""
        self.index_message(conv_id, msg_id, role, content, ts)
        self.vectorize_pending()

    # --- Délégation : pondération/consolidation ------------------------------

    def adjust_weight(self, conv_id: str, msg_id: str, delta: float,
                      conversations=None) -> int:
        """Ajuste le poids d'un souvenir (feedback), clampe et ajuste le précédent."""
        wc = WeightConsolidator(self._data["documents"])
        count = wc.apply_weight(conv_id, msg_id, delta, WEIGHT_MIN, WEIGHT_MAX)
        prev_id = wc.preceding_user_msg_id(conversations, conv_id, msg_id)
        if prev_id and delta:
            count += wc.apply_weight(conv_id, prev_id, delta * 0.5, WEIGHT_MIN, WEIGHT_MAX)
        if count:
            self._save()
            self.clear_cache()
        return count

    def consolidate(self):
        """Consolidation hors ligne : dedup + prune (index only, best-effort)."""
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
            self._save()
        self.clear_cache()

    # --- Délégation : recherche + cache --------------------------------------

    def clear_cache(self):
        self._cache.clear()

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not query or not self._data["documents"]:
            return []
        now = self._now()
        cached = self._cache.get(query, top_k, now)
        if cached is not None:
            return cached
        query_vec = np.array(self._embed(query), dtype=np.float32)
        self._embed_pending()
        all_results = cosine_search(query_vec, self._data["documents"], top_k=len(self._data["documents"]))
        results = WeightConsolidator(self._data["documents"]).score_and_rank(all_results, top_k, now)
        self._cache.put(query, top_k, results, now)
        return results

    # --- Stats (observabilité) -----------------------------------------------

    def _conversation_weights(self) -> list:
        return [
            d.get("metadata", {}).get("weight", 1.0)
            for d in self._data["documents"]
            if d.get("metadata", {}).get("source") == "conversation"
        ]

    def _weight_stats(self, conv_weights: list) -> tuple:
        if not conv_weights:
            return 0.0, 0.0
        mean = round(sum(conv_weights) / len(conv_weights), 3)
        low = round(sum(1 for w in conv_weights if w <= 0) / len(conv_weights), 3)
        return mean, low

    def _estimate_dedup(self) -> int:
        text_counts = {}
        for d in self._data["documents"]:
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
        """Statistiques de l'index (total, embeddés, cache, poids, dedup, migration)."""
        docs = self._data["documents"]
        total = len(docs)
        embedded = sum(1 for d in docs if d.get("embedding") is not None)
        conv_weights = self._conversation_weights()
        wm, lw = self._weight_stats(conv_weights)
        return {
            "total": total, "embedded": embedded, "pending": total - embedded,
            "cache_hits": self._cache_hits, "cache_misses": self._cache_misses,
            "cache_hit_rate": self._cache_hit_rate(),
            "embedding_backend": "ollama" if self._embedder._inference else "fallback_histogram",
            "embedding_model": EXPECTED_MODEL, "embedding_dim": EXPECTED_DIM,
            "stored_dim": self._data.get("embedding_dim"),
            "migration_status": self.last_migration,
            "using_fallback": self._embedder.using_fallback,
            "weight_mean": wm, "low_weight_ratio": lw,
            "conversation_docs": len(conv_weights), "message_indexed": len(conv_weights),
            "dedup_estimated": self._estimate_dedup(),
            "last_consolidation": self._data.get("last_consolidation"),
            "consolidation_runs": self._data.get("consolidation_runs", 0),
        }

    def is_healthy(self) -> bool:
        """Vérifie que l'index est valide : fichier lisible + structure correcte."""
        if not os.path.exists(VECTOR_PATH):
            return True  # Pas encore créé = sain
        try:
            with open(VECTOR_PATH) as f:
                data = json.load(f)
            return isinstance(data, dict) and "documents" in data
        except (json.JSONDecodeError, OSError):
            return False
