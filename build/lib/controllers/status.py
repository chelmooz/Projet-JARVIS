"""Statut des services — healthcheck Ollama + cache periodique.

Les dependances (memory, vector, log, ctx) sont passees en parametres
via AppContext pour eviter l'import circulaire avec controllers.context.
"""

import logging
import threading
import time

from config.paths import OLLAMA_PORT
from controllers.di import AppContext
from services.adapters.ollama_adapter import OllamaAdapter

_logger = logging.getLogger("jarvis.context")


def _check_ollama() -> bool:
    """Verifie si le serveur Ollama *portable* (OLLAMA_PORT=11436) repond.

    On ignore volontairement tout Ollama systeme sur 11434 : le backend est
    fige sur le portable, et signaler un Ollama systeme comme "disponible"
    mentirait a l'UI (cf. design portable, jarvis.py:_start_ollama_backend).

    Teste plusieurs hotes car Ollama peut ecouter en IPv4 (127.0.0.1) ou en
    IPv6 (::1 via 'localhost') selon la plateforme / la config OLLAMA_HOST.
    Passe par OllamaAdapter pour respecter l'architecture ports-and-adapters.
    """
    hosts = ("http://localhost", "http://127.0.0.1")
    return any(OllamaAdapter._check_endpoint(f"{host}:{OLLAMA_PORT}") for host in hosts)


def _build_status_data(ctx: AppContext, ollama_ok: bool, active_backend: str, vector_stats: dict) -> dict:
    """Construit le dictionnaire de statut des services (hors verrou)."""
    memory_ok = ctx.memory.is_healthy() if ctx.memory is not None else False
    vector_ok = ctx.vector.is_healthy() if ctx.vector is not None else False
    return {
        "backend": active_backend,
        "ollama": ollama_ok,
        "memory_ok": memory_ok,
        "vector_ok": vector_ok,
        "vector": vector_stats,
        "init_report": ctx.init_report,
        "ready": ctx.ready,
    }


def _refresh_status_cache(ctx: AppContext, cache_lock: threading.Lock, ollama_ok: bool | None = None):
    """Rafraichit le cache de statut des services (meme en mode degrade)."""
    if ollama_ok is None:
        ollama_ok = _check_ollama()
    active_backend = (
        ctx.inference.get_active_backend().split("(")[0].strip()
        if ctx.inference is not None else "ollama"
    )
    vector_stats = ctx.vector.stats() if ctx.vector is not None else {}
    if vector_stats.get("using_fallback"):
        ctx.log.log("ERROR", "Embedding backend indisponible — fallback histogramme actif")
    with cache_lock:
        ctx.status_cache["ts"] = time.time()
        ctx.status_cache["data"] = _build_status_data(ctx, ollama_ok, active_backend, vector_stats)


def _status_refresher(ctx: AppContext, stop_event: threading.Event, refresh_interval: int):
    """Boucle periodique : rafraichit le cache de statut toutes les N secondes."""
    while not stop_event.is_set():
        if stop_event.wait(refresh_interval):
            break
        try:
            _refresh_status_cache(ctx, ctx.cache_lock)
        except Exception as e:
            _logger.exception("_status_refresher: echec du rafraichissement du cache: %s", e)
