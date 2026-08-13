"""Cache LRU des résultats de recherche vectorielle avec expiration TTL.

Responsabilité unique (SRP) : conserver les résultats de recherche déjà
calculés pour éviter de recalculer les requêtes identiques, en appliquant
une stratégie LRU (Least Recently Used) et un TTL (Time To Live) horodaté.

Thread-safe : toutes les opérations de lecture/écriture sont protégées
par un verrou (RLock) pour éviter les race conditions en environnement
concurrent (ex: FastAPI threadpool).
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

import numpy as np

from config.constants import vector_cache_size

# Durée de validité des entrées du cache (secondes)
VECTOR_CACHE_TTL_SECONDS = 300


class MatrixCache:
    """Cache de la matrice normalisée des embeddings (documents + matrice).

    Évite de re-normaliser tous les embeddings à chaque recherche : la
    matrice est construite une fois puis enrichie par ``append`` (vstack
    incrémental) quand de nouveaux documents avec embeddings arrivent.
    """

    def __init__(self) -> None:
        self._data: tuple[list[dict[str, Any]], np.ndarray | None] | None = None

    def get(self) -> tuple[list[dict[str, Any]], np.ndarray | None] | None:
        """Retourne (valid_docs, matrice normalisée) ou None si non construit."""
        return self._data

    def set(self, data: tuple[list[dict[str, Any]], np.ndarray | None]) -> None:
        """Remplace entièrement le contenu du cache."""
        self._data = data

    def clear(self) -> None:
        """Vide le cache."""
        self._data = None

    def append(self, new_docs: list[dict[str, Any]], new_embeddings: np.ndarray) -> None:
        """Ajoute de nouveaux embeddings normalisés à la matrice existante.

        Ne fait rien si le cache n'existe pas encore (premier build à la
        première recherche).
        """
        if self._data is None:
            return

        valid_docs, matrix = self._data
        if matrix is None or len(matrix) == 0:
            return

        # Filtrer et normaliser les nouveaux embeddings (même logique que build_normalized_matrix)
        new_valid = []
        new_vecs = []
        for doc, emb in zip(new_docs, new_embeddings):
            if emb is not None:
                vec = np.asarray(emb, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    new_valid.append(doc)
                    new_vecs.append(vec / norm)

        if new_valid:
            new_matrix = np.vstack([matrix, np.array(new_vecs, dtype=np.float32)])
            self._data = (valid_docs + new_valid, new_matrix)


class VectorCache:
    """Cache LRU + TTL pour les résultats de recherche vectorielle.

    La clé de cache associe le texte de la requête et le top_k, car deux
    recherches avec un top_k différent produisent des résultats distincts.
    La valeur stockée est un tuple (timestamp, résultats) permettant la
    vérification du TTL lors de la lecture.
    """

    def __init__(self, max_size: int | None = None, ttl_seconds: int = VECTOR_CACHE_TTL_SECONDS) -> None:
        """Initialise le cache avec sa capacité maximale et son TTL.

        Si max_size est None, la taille dépend du profil (low I/O => plus petit
        cache, moins d'empreinte mémoire sur clef USB lente).
        """
        self._max_size = max_size if max_size is not None else vector_cache_size()
        self._ttl = ttl_seconds
        self._store: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._lock = threading.RLock()

    def _key(self, query_text: str, top_k: int) -> str:
        """Construit la clé de cache à partir de la requête et du top_k."""
        return f"{query_text}:{top_k}"

    def get(self, query_text: str, top_k: int, now: float) -> list[dict[str, Any]] | None:
        """Retourne le résultat en cache ou None (vérifie le TTL, gère le LRU)."""
        key = self._key(query_text, top_k)
        with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                timestamp, cached = entry
                if now - timestamp <= self._ttl:
                    self._hits += 1
                    self._store.move_to_end(key)
                    return cached
                del self._store[key]
            self._misses += 1
        return None

    def put(self, query_text: str, top_k: int, results: list[dict[str, Any]], now: float) -> None:
        """Stocke un résultat et applique la limite de taille LRU."""
        key = self._key(query_text, top_k)
        with self._lock:
            self._store[key] = (now, results)
            if len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def clear(self) -> None:
        """Vide les entrées du cache sans réinitialiser les compteurs de stats."""
        with self._lock:
            self._store.clear()

    @property
    def hits(self) -> int:
        """Nombre de lectures ayant abouti sur une entrée valide."""
        with self._lock:
            return self._hits

    @property
    def misses(self) -> int:
        """Nombre de lectures ayant nécessité un recalcul."""
        with self._lock:
            return self._misses

    def __len__(self) -> int:
        """Nombre d'entrées actuellement présentes dans le cache."""
        with self._lock:
            return len(self._store)


__all__ = ["VECTOR_CACHE_TTL_SECONDS", "VectorCache"]
