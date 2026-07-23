"""Utilitaires atomiques et thread-safe pour les opérations fichier.

Fournit :
- Un décorateur ``retry`` pour les opérations I/O sujettes aux erreurs transitoires.
- ``read_json`` / ``write_json_atomic`` : lecture/écriture JSON thread-safe et atomique.

Toutes les fonctions sont synchrones (``time.sleep`` conservé dans ``retry`` car
la rendre async casserait l'API des fonctions décorées).
"""

from __future__ import annotations

import functools
import json
import logging
import os
import threading
import time
from typing import Any, Callable, TypeVar

_logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

_FILE_LOCKS: dict[str, threading.Lock] = {}
_global_lock = threading.Lock()


def retry(max_attempts: int = 3, delay: float = 0.25) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Décorateur : réessaie une fonction jusqu'à ``max_attempts`` fois.

    Attend ``delay`` secondes entre chaque tentative. La dernière exception
    levée est propagée si toutes les tentatives échouent.

    Note : ``time.sleep`` est conservé (fonction sync générique). Rendre ce
    décorateur async casserait l'API des fonctions décorées (``read_json``,
    ``write_json_atomic``).
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def _get_lock(path: str) -> threading.Lock:
    """Retourne un verrou dédié à un chemin fichier (créé à la demande)."""
    with _global_lock:
        if path not in _FILE_LOCKS:
            _FILE_LOCKS[path] = threading.Lock()
        return _FILE_LOCKS[path]


@retry()
def read_json(path: str, default: Any = None) -> Any:
    """Lit un fichier JSON avec fallback silencieux.

    En cas d'erreur (fichier absent, JSON invalide), retourne ``default``
    si fourni, sinon un dictionnaire vide ``{}``.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _logger.debug("Failed to read JSON %s: %s", path, e)
        return default if default is not None else {}


@retry()
def write_json_atomic(path: str, data: Any, **json_kwargs: Any) -> None:
    """Écriture atomique thread-safe (tmp + ``os.replace``).

    Garantit que le fichier n'est jamais corrompu : soit l'écriture entière
    réussit, soit le fichier original reste intact. Un verrou par chemin
    évite les écritures concurrentes.
    
    CORRECTION : Conversion explicite de ``path`` en ``str`` pour compatibilité
    avec les objets ``pathlib.Path`` (WindowsPath/PosixPath).
    """
    # CORRECTION : Cast path en str pour compatibilité Path/str
    path = str(path)
    
    lock = _get_lock(path)
    with lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, **json_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)


__all__ = ["retry", "read_json", "write_json_atomic"]