"""Rate limiter middleware — simple bucket par IP."""
import threading
import time
from collections import defaultdict

# --- État global du rate limiter ---
# _hits : dictionnaire IP -> liste de timestamps (secondes)
# Chaque appel enregistre l'instant présent, on nettoie les entrées > 60s
_lock = threading.Lock()
_hits: dict[str, list[float]] = defaultdict(list)
MAX_REQUESTS = 500
WINDOW = 60


def check_rate_limit(client_ip: str) -> tuple[bool, int]:
    """Vérifie si l'IP n'a pas dépassé le quota de 60 requêtes par minute.

    Retourne (allowed, remaining) où remaining est le nombre de requêtes
    restantes dans la fenêtre courante (après déduction de celle-ci).
    """
    now = time.time()
    cutoff = now - WINDOW
    with _lock:
        window = [t for t in _hits[client_ip] if t > cutoff]
        window.append(now)
        _hits[client_ip] = window
        count = len(window)
        remaining = MAX_REQUESTS - count
        return remaining >= 0, max(remaining, 0)
