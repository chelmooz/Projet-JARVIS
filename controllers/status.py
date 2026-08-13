"""Statut des services — healthcheck Ollama + cache periodique.

Les dependances (memory, vector, log, ctx) sont passees en parametres
via AppContext pour eviter l'import circulaire avec controllers.context.

Note : ce module est legacy — la route moderne /api/status/stream lit le
cache depuis ``app.state.status_cache`` (voir controllers/routes/system.py).
Ces helpers sont conservés pour compatibilité des tests.
"""

import logging
import threading
import time
from typing import Any

from config.constants import VERSION
from controllers.di import AppContext

_logger = logging.getLogger("jarvis.context")

_LOCK_FALLBACK = threading.Lock()


def _service_healthy(service: Any) -> bool:
    """État de santé défensif d'un service (``is_healthy()`` optionnel)."""
    check = getattr(service, "is_healthy", None)
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:
        _logger.warning("Service health check failed", exc_info=True)
        return False


def build_status(context: Any) -> dict[str, Any]:
    """Construit le dict de status à partir du contexte (état des services).

    Source unique pour les endpoints API (/api/status, /api/status/stream).
    Remplace les globales legacy ``_check_ollama`` / ``_refresh_status_cache``
    de l'ancien ``context.py`` : l'état est dérivé des ports (``ping`` /
    ``is_healthy``), sans état global mutable.
    """
    inference = getattr(context, "inference", None)
    ollama_up = False
    if inference is not None and hasattr(inference, "ping"):
        try:
            ollama_up = bool(inference.ping())
        except Exception:
            _logger.warning("Inference ping failed", exc_info=True)
            ollama_up = False
    return {
        "ollama": ollama_up,
        "inference": _service_healthy(inference),
        "vector": _service_healthy(getattr(context, "vector", None)),
        "memory": _service_healthy(getattr(context, "memory", None)),
        "conversations": _service_healthy(getattr(context, "conversations", None)),
        "version": VERSION,
    }


def _check_ollama(ctx: AppContext) -> bool:
    """Verifie si le serveur Ollama *portable* (OLLAMA_PORT=11436) repond.

    On ignore volontairement tout Ollama systeme sur 11434 : le backend est
    fige sur le portable, et signaler un Ollama systeme comme "disponible"
    mentirait a l'UI (cf. design portable, jarvis.py:_start_ollama_backend).

    Utilise l'instance d'adaptateur partagee depuis AppContext pour respecter
    l'architecture ports-and-adapters (base_url configuree dans l'instance).
    """
    if ctx.inference is None:
        return False
    return ctx.inference.ping()


def _build_status_data(
    ctx: AppContext, ollama_ok: bool, active_backend: str, vector_stats: dict[str, Any]
) -> dict[str, Any]:
    """Construit le dictionnaire de statut des services (hors verrou).

    Legacy — conservé pour compatibilité du cache de statut (AppContext.status_cache).
    """
    memory_ok = ctx.memory.is_healthy() if ctx.memory is not None else False
    vector_ok = ctx.vector.is_healthy() if ctx.vector is not None else False
    return {
        "backend": active_backend,
        "ollama": ollama_ok,
        "memory_ok": memory_ok,
        "vector_ok": vector_ok,
        "vector": vector_stats,
        "init_report": getattr(ctx, "init_report", None),
        "ready": bool(getattr(ctx, "ready", False)),
    }


def _refresh_status_cache(ctx: AppContext, cache_lock: threading.Lock, ollama_ok: bool | None = None) -> None:
    """Rafraichit le cache de statut des services (meme en mode degrade)."""
    if ollama_ok is None:
        ollama_ok = _check_ollama(ctx)
    active_backend = ctx.inference.get_active_backend().split("(")[0].strip() if ctx.inference is not None else "ollama"
    vector_stats = ctx.vector.stats() if ctx.vector is not None else {}
    if vector_stats.get("using_fallback") and ctx.log is not None:
        ctx.log.log("ERROR", "Embedding backend indisponible — fallback histogramme actif")
    with cache_lock:
        ctx.status_cache["ts"] = time.time()
        ctx.status_cache["data"] = _build_status_data(ctx, ollama_ok, active_backend, vector_stats)


def _status_refresher(ctx: AppContext, stop_event: threading.Event, refresh_interval: int) -> None:
    """Boucle periodique : rafraichit le cache de statut toutes les N secondes."""
    while not stop_event.is_set():
        if stop_event.wait(refresh_interval):
            break
        try:
            _refresh_status_cache(ctx, getattr(ctx, "cache_lock", _LOCK_FALLBACK))
        except Exception as e:
            _logger.exception("_status_refresher: echec du rafraichissement du cache: %s", e)
