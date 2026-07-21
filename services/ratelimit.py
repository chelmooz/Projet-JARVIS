"""Rate limiter middleware — simple bucket par IP.

Responsabilité unique (SRP) :
- Limiter le nombre de requêtes par adresse IP sur une fenêtre glissante.
- Garantir la thread-safety des accès concurrents (Lock).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Tuple

# --- État global du rate limiter ---
# _hits : dictionnaire IP -> liste de timestamps (secondes)
# Chaque appel enregistre l'instant présent, on nettoie les entrées > WINDOW
_lock = threading.Lock()
_hits: dict[str, list[float]] = defaultdict(list)

MAX_REQUESTS = 500
WINDOW = 60  # Fenêtre glissante en secondes


def check_rate_limit(client_ip: str) -> Tuple[bool, int]:
    """Vérifie si l'IP n'a pas dépassé le quota de MAX_REQUESTS requêtes par WINDOW secondes.

    Retourne (allowed, remaining) où remaining est le nombre de requêtes
    restantes dans la fenêtre courante (après déduction de celle-ci).
    """
    now = time.time()
    cutoff = now - WINDOW
    
    with _lock:
        # Filtrage des timestamps expirés (fenêtre glissante)
        window = [t for t in _hits[client_ip] if t > cutoff]
        window.append(now)
        _hits[client_ip] = window
        
        count = len(window)
        remaining = MAX_REQUESTS - count
        
        return remaining >= 0, max(remaining, 0)


__all__ = ["check_rate_limit", "MAX_REQUESTS", "WINDOW"]
