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

from config.constants import vector_cache_size

# Durée de validité des entrées du cache (secondes)
VECTOR_CACHE_TTL_SECONDS = 300


class VectorCache:
    """Cache LRU + TTL pour les résultats de recherche vectorielle.

    La clé de cache associe le texte de la requête et le top_k, car deux
    recherches avec un top_k différent produisent des résultats distincts.
    La valeur stockée est un tuple (timestamp, résultats) permettant la
    vérification du TTL lors de la lecture.
    """

    def __init__(
        self, max_size: int | None = None, ttl_seconds: int = VECTOR_CACHE_TTL_SECONDS
    ) -> None:
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
        """Vide intégralement le cache et réinitialise les compteurs."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

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
