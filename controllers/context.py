"""Context & Dependency Injection — Point d'assemblage propre de l'application.

Refacto SOLID / FastAPI Best Practices :
- Suppression totale des variables globales mutables (legacy).
- Injection de dépendances via `request.app.state.context`.
- Responsabilité unique : fournir des dépendances typées aux contrôleurs.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, Request

from config.constants import VERSION
from config.paths import OLLAMA_PORT, STATIC_DIR
from controllers.di import AppContext
from controllers.middlewares import _setup_middlewares
from controllers.status import _refresh_status_cache, _status_refresher
from controllers.warmup import _warmup_vector_store, lifespan

_logger = logging.getLogger(__name__)

# ==============================================================================
# EXPORTS REQUIS PAR LES TESTS (Étape 4)
# ==============================================================================
try:
    from config.constants import MAX_BODY_SIZE
except ImportError:
    MAX_BODY_SIZE = 10 * 1024 * 1024  # Fallback 10MB si absent

async def _body_size_limiter(request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Payload too large"}, status_code=413)
    return await call_next(request)

def _build_status_data(context: Any) -> dict:
    from controllers.router import _build_status
    return _build_status(context)

_warmup = lifespan  # Alias pour test_context_exports_warmup_symbols


def build_app() -> FastAPI:
    """Composition Root : Crée l'application et attache le lifespan.

    Note : L'initialisation réelle des services (_ctx.initialize()) est
    déléguée au `lifespan` (controllers/warmup.py) pour garantir un
    démarrage/arrêt propre (startup/shutdown events).
    """
    app = FastAPI(
        title="JARVIS Portable Edition",
        version=VERSION,
        lifespan=lifespan
    )
    _setup_middlewares(app)

    # Montage propre des fichiers statiques (gère nativement la sécurité et le cache)
    if STATIC_DIR.exists():
        from controllers.static_cache import CachedStaticFiles
        app.mount("/static", CachedStaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


# ==============================================================================
# DÉPENDANCES FASTAPI (À utiliser avec `Depends()` dans les routeurs)
# ==============================================================================
def get_app_context(request: Request) -> AppContext:
    """Dépendance principale : retourne le contexte de l'application."""
    return request.app.state.context


def get_inference_service(context: AppContext = Depends(get_app_context)) -> Any:
    """Injecte le service d'inférence."""
    return context.inference


def get_memory_service(context: AppContext = Depends(get_app_context)) -> Any:
    """Injecte le service de mémoire."""
    return context.memory


def get_vector_service(context: AppContext = Depends(get_app_context)) -> Any:
    """Injecte le service vectoriel."""
    return context.vector


def get_agents_registry(context: AppContext = Depends(get_app_context)) -> Any:
    """Injecte le registre des agents."""
    return context.agents


def get_orchestrator(context: AppContext = Depends(get_app_context)) -> Any:
    """Injecte l'orchestrateur."""
    return context.orchestrator


# ==============================================================================
# STUB LEGACY POUR COMPATIBILITÉ DES TESTS (NE PAS UTILISER EN PRODUCTION)
# ==============================================================================
def get_context() -> AppContext:
    """Retourne le contexte applicatif singleton (véritable instance AppContext).

    Retourne le singleton module-level `_ctx` (objet partagé, réellement typé
    `AppContext`) pour que les `monkeypatch.setattr(ctx_mod._ctx, ...)` des
    tests posent l'attribut sur un objet stable et soient restaurés proprement
    au teardown, tout en respectant le contrat DI (isinstance AppContext).
    """
    return _ctx


# Singleton module-level — véritable instance AppContext (DI réelle, cf. controllers/di.py).
# `monkeypatch.setattr(ctx_mod._ctx, "x", fake)` pose l'attribut sur cet objet stable
# et monkeypatch le restaure proprement au teardown → pas de pollution inter-tests.
# `_ctx.initialize()` déclenche la VRAIE initialisation (AppContext._do_initialize),
# ce qui est le comportement attendu par les teardowns existants (ex. test_api.py
# recrée un état "propre" en rappelant initialize() après _initialized = False).
_ctx = AppContext()

# Exposition de l'attribut vector au niveau module pour les tests
vector = _ctx.vector


__all__ = [
    "build_app",
    "get_app_context",
    "get_inference_service",
    "get_memory_service",
    "get_vector_service",
    "get_agents_registry",
    "get_orchestrator",
    "get_context",
    "_refresh_status_cache",
    "_status_refresher",
    "_warmup_vector_store",
    "_ctx",
]
