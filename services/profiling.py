"""Profiling des endpoints lents — store en mémoire thread-safe.

Détecte les requêtes dépassant SLOW_THRESHOLD secondes et conserve
l'historique des routes lentes pour exposition dans /api/status.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any, TypedDict

# Seuil de lenteur (secondes) — surchargeable pour les tests.
SLOW_THRESHOLD: float = float(os.environ.get("JARVIS_SLOW_THRESHOLD", "1.0"))

MAX_RECENT: int = 50


class EndpointStats(TypedDict):
    """Statistiques agrégées d'une route lente."""
    max_dur: float
    count: int


class RecentSlowRequest(TypedDict):
    """Requête lente récente enregistrée."""
    route: str
    duration: float
    ts: float


_lock = threading.Lock()
_store: dict[str, EndpointStats] = {}
_recent: list[RecentSlowRequest] = []


def record_slow(route: str, duration: float) -> None:
    """Enregistre une requête lente pour une route donnée (thread-safe)."""
    with _lock:
        entry = _store.get(route)
        if entry is None:
            _store[route] = {"max_dur": duration, "count": 1}
        else:
            entry["max_dur"] = max(entry["max_dur"], duration)
            entry["count"] += 1
        
        _recent.append({"route": route, "duration": duration, "ts": time.time()})
        if len(_recent) > MAX_RECENT:
            # Troncature efficace de la liste (in-place)
            _recent[:] = _recent[-MAX_RECENT:]


def get_slow_endpoints() -> list[dict[str, Any]]:
    """Retourne la liste des routes lentes (max durée + compteur), triée par route."""
    with _lock:
        return [
            {"route": r, "max_duration": v["max_dur"], "count": v["count"]}
            for r, v in sorted(_store.items())
        ]


def reset_profiling() -> None:
    """Réinitialise le store (utilisé principalement par les tests)."""
    with _lock:
        _store.clear()
        _recent.clear()


__all__ = [
    "SLOW_THRESHOLD",
    "record_slow",
    "get_slow_endpoints",
    "reset_profiling",
]
