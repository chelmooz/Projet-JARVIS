"""Utilitaires atomiques et thread-safe pour les opérations fichier."""
import functools
import json
import logging
import os
import threading
import time

_logger = logging.getLogger(__name__)

_FILE_LOCKS: dict[str, threading.Lock] = {}
_global_lock = threading.Lock()


def retry(max_attempts: int = 3, delay: float = 0.25):
    """Décorateur : réessaie une fonction jusqu'à max_attempts fois avec un délai entre chaque tentative."""
    def decorator(func):
        """Decorator."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper."""
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        # time.sleep conserve : fonction sync generique du decorateur retry ;
                        # la rendre async casserait l'API des fonctions decorées (read_json, write_json_atomic)
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


def _get_lock(path: str) -> threading.Lock:
    """ get lock."""
    with _global_lock:
        if path not in _FILE_LOCKS:
            _FILE_LOCKS[path] = threading.Lock()
        return _FILE_LOCKS[path]


@retry()
def read_json(path: str, default=None):
    """Lit un fichier JSON avec fallback silencieux."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _logger.debug("Failed to read JSON %s: %s", path, e)
        return default if default is not None else {}


@retry()
def write_json_atomic(path: str, data, **json_kwargs):
    """Écriture atomique thread-safe (tmp + os.replace).

    Garantit que le fichier n'est jamais corrompu : soit l'écriture entière
    réussit, soit le fichier original reste intact.
    """
    lock = _get_lock(path)
    with lock:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, **json_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
