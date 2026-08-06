"""Rate limiter middleware — simple bucket par IP.

Responsabilité unique (SRP) :
- Limiter le nombre de requêtes par adresse IP sur une fenêtre glissante.
- Garantir la thread-safety des accès concurrents (Lock).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict

# --- État global du rate limiter ---
# _hits : dictionnaire IP -> liste de timestamps (secondes)
# Chaque appel enregistre l'instant présent, on nettoie les entrées > WINDOW
_lock = threading.Lock()
_hits: dict[str, list[float]] = defaultdict(list)

# Horodatage de la dernière purge : la purge est throttlée à 1/WINDOW pour
# éviter un scan complet du dict à chaque requête.
_last_purge: float = 0.0

MAX_REQUESTS = 500
WINDOW = 60  # Fenêtre glissante en secondes


def _purge_stale(cutoff: float | None = None) -> int:
    """Nettoie les IPs sans activité depuis plus de WINDOW secondes.

    Retourne le nombre d'IPs purgées. Appel possible depuis un thread
    d'arrière-plan ou entre deux requêtes. ``cutoff`` est optionnel :
    s'il est fourni, il évite un second appel à ``time.time()`` (cas
    check_rate_limit → purge).
    """
    if cutoff is None:
        cutoff = time.time() - WINDOW
    purged = 0
    with _lock:
        stale = [ip for ip, ts in _hits.items() if ts and not any(t > cutoff for t in ts)]
        for ip in stale:
            del _hits[ip]
            purged += 1
    return purged


def check_rate_limit(client_ip: str) -> tuple[bool, int]:
    """Vérifie si l'IP n'a pas dépassé le quota de MAX_REQUESTS requêtes par WINDOW secondes.

    Retourne (allowed, remaining) où remaining est le nombre de requêtes
    restantes dans la fenêtre courante (après déduction de celle-ci).
    """
    global _last_purge
    now = time.time()
    cutoff = now - WINDOW

    # Purge périodique des IPs mortes (au plus 1 fois par WINDOW) — évite la
    # fuite mémoire lente sur les IPs qui ne reviennent jamais.
    if now - _last_purge >= WINDOW:
        _purge_stale(cutoff)
        _last_purge = now

    with _lock:
        # Filtrage des timestamps expirés (fenêtre glissante)
        window = [t for t in _hits[client_ip] if t > cutoff]
        window.append(now)
        _hits[client_ip] = window

        count = len(window)
        remaining = MAX_REQUESTS - count

        return remaining >= 0, max(remaining, 0)


__all__ = ["check_rate_limit", "MAX_REQUESTS", "WINDOW"]
