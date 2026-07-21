"""Profiling des endpoints lents — store en mémoire thread-safe.

Détecte les requêtes dépassant SLOW_THRESHOLD secondes et conserve
l'historique des routes lentes pour exposition dans /api/status.
"""
import os
import threading
import time

# Seuil de lenteur (secondes) — surchargeable pour les tests.
SLOW_THRESHOLD = float(os.environ.get("JARVIS_SLOW_THRESHOLD", "1.0"))

MAX_RECENT = 50

_lock = threading.Lock()
# route -> {"max_dur": float, "count": int}
_store: dict[str, dict] = {}
# historique récent borné
_recent: list[dict] = []


def record_slow(route: str, duration: float):
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
            _recent[:] = _recent[-MAX_RECENT:]


def get_slow_endpoints() -> list[dict]:
    """Retourne la liste des routes lentes (max durée + compteur)."""
    with _lock:
        return [
            {"route": r, "max_duration": v["max_dur"], "count": v["count"]}
            for r, v in sorted(_store.items())
        ]


def reset_profiling():
    """Réinitialise le store (utilisé par les tests)."""
    with _lock:
        _store.clear()
        _recent.clear()
