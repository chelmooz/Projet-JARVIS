"""Façade de compatibilité — Point d'assemblage de l'application FastAPI.

⚠️ CE MODULE EST EN DETTE TECHNIQUE.
Les exports module-level (inference, memory, etc.) sont dépréciés.
Toute nouvelle route doit utiliser `request.app.state.context` ou `Depends(get_context)`.
"""
import logging
import os
import threading

from fastapi import FastAPI

from config.constants import CORS_ORIGIN, MAX_BODY_SIZE, REFRESH_INTERVAL, STATIC_DIR, VERSION
from config.paths import OLLAMA_PORT
from controllers.di import AppContext
from controllers.middlewares import _body_size_limiter, _setup_middlewares
from controllers.status import (
    _build_status_data,
    _check_ollama,
    _refresh_status_cache,
    _status_refresher,
)
from controllers.warmup import (
    _warmup,
    _warmup_default_model,
    _warmup_vector_store,
    lifespan,
)
from services.profiling import SLOW_THRESHOLD

_logger = logging.getLogger("jarvis.context")

# Conteneur de services (Composition Root)
_ctx = AppContext()

# --- Exports Legacy (Déprécié) ---
# Ces variables ne doivent plus être utilisées. Migrez vers get_context().
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

# Déclaration explicite de l'API publique du module (satisfait les linters)
__all__ = [
    "get_context", "build_app", "cache_lock",
    # Legacy exports
    "inference", "memory", "vector", "log", "analytics",
    "conversations", "metrics", "agents", "router_svc", "orchestrator",
    "status_cache", "PROFILES_PATH", "_stop_event",
    # Re-exports pour compatibilité
    "CORS_ORIGIN", "MAX_BODY_SIZE", "REFRESH_INTERVAL", "STATIC_DIR", "VERSION",
    "OLLAMA_PORT", "_body_size_limiter", "_setup_middlewares",
    "_build_status_data", "_check_ollama", "_refresh_status_cache", "_status_refresher",
    "_warmup", "_warmup_default_model", "_warmup_vector_store", "lifespan",
    "SLOW_THRESHOLD",
]


def get_context() -> AppContext:
    """Retourne le conteneur de services (Source de vérité)."""
    return _ctx


def _bind_legacy_exports(ctx: AppContext):
    """Assigne explicitement les globals legacy (à supprimer après migration des routes)."""
    global inference, memory, vector, log, analytics
    global conversations, metrics, agents, router_svc, orchestrator, status_cache
    
    inference = ctx.inference
    memory = ctx.memory
    vector = ctx.vector
    log = ctx.log
    analytics = ctx.analytics
    conversations = ctx.conversations
    metrics = ctx.metrics
    agents = ctx.agents
    router_svc = ctx.router_svc
    orchestrator = ctx.orchestrator
    status_cache = ctx.status_cache


def _register_routes(app: FastAPI):
    if os.path.exists(STATIC_DIR):
        from controllers.static_cache import CachedStaticFiles
        app.mount("/static", CachedStaticFiles(directory=STATIC_DIR), name="static")


def build_app() -> FastAPI:
    """Composition Root : Initialise les services et assemble l'application."""
    # Fail Fast : Si l'initialisation échoue, l'application ne doit pas démarrer en mode dégradé silencieux.
    _ctx.initialize()
    _bind_legacy_exports(_ctx)

    app = FastAPI(
        title="JARVIS Portable Edition",
        version=VERSION,
        lifespan=lifespan
    )
    
    # Attache le contexte à l'app pour l'injection de dépendances moderne
    app.state.context = _ctx

    _setup_middlewares(app)
    _register_routes(app)
    
    return app
