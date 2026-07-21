"""Façade de compatibilité — expose les singletons et fonctions pour l'API legacy.

Ce module maintient les imports legacy (controllers.context.inference, etc.)
en synchronisant les singletons module-level avec AppContext après initialize().

Architecture propre :
- controllers.di → AppContext (conteneur de services)
- controllers.middlewares → middlewares FastAPI
- controllers.status → healthcheck Ollama + cache
- controllers.warmup → warmup asynchrone + lifespan FastAPI
- controllers.context → façade de compatibilité (ce module)
"""

import logging
import os
import threading

from fastapi import FastAPI

from config.constants import CORS_ORIGIN, MAX_BODY_SIZE, REFRESH_INTERVAL, STATIC_DIR, VERSION  # noqa: F401
from config.paths import OLLAMA_PORT  # noqa: F401
from controllers.di import AppContext
from controllers.middlewares import _body_size_limiter, _setup_middlewares  # noqa: F401
from controllers.status import (  # noqa: F401
    _build_status_data,
    _check_ollama,
    _refresh_status_cache,
    _status_refresher,
)
from controllers.warmup import (  # noqa: F401
    _warmup,
    _warmup_default_model,
    _warmup_vector_store,
    lifespan,
)
from services.profiling import SLOW_THRESHOLD  # noqa: F401

_logger = logging.getLogger("jarvis.context")

# Conteneur leger (None) a l'import — initialize() appele dans build_app()
_ctx = AppContext()

# Singletons module-level : None jusqu'a initialize()
inference = None
memory = None
vector = None
log = None
analytics = None
conversations = None
metrics = None
agents = None
router_svc = None
orchestrator = None
status_cache = _ctx.status_cache
PROFILES_PATH = _ctx.profiles_path
_stop_event = _ctx.stop_event
cache_lock = threading.Lock()


def _sync_module_globals(ctx: AppContext):
    """Synchronise les singletons module-level apres initialize()."""
    g = globals()
    for attr in ("inference", "memory", "vector", "log", "analytics",
                 "conversations", "metrics", "agents", "router_svc",
                 "orchestrator"):
        g[attr] = getattr(ctx, attr)
    g["status_cache"] = ctx.status_cache


def get_context() -> AppContext:
    """Retourne le singleton AppContext (injection de dependances)."""
    return _ctx


def _register_routes(app):
    if os.path.exists(STATIC_DIR):
        from controllers.static_cache import CachedStaticFiles
        app.mount("/static", CachedStaticFiles(directory=STATIC_DIR), name="static")


def build_app():
    try:
        _ctx.initialize()
        _sync_module_globals(_ctx)
    except Exception as e:  # ne jamais empecher uvicorn de demarrer
        _logger.exception("build_app: initialize/echec sync — mode degrade: %s", e)
    app = FastAPI(title="JARVIS Portable Edition", version=VERSION, lifespan=lifespan)
    try:
        _setup_middlewares(app)
        _register_routes(app)
    except Exception as e:
        _logger.exception("build_app: setup des routes/middlewares a leve: %s", e)
    return app
