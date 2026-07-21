"""Context & Dependency Injection — Point d'assemblage propre de l'application.

Refacto SOLID / FastAPI Best Practices :
- Suppression totale des variables globales mutables (legacy).
- Injection de dépendances via ``request.app.state.context``.
- Responsabilité unique : fournir des dépendances typées aux contrôleurs.

Le typage de retour des helpers d'injection est **inféré** depuis les
attributs de :class:`AppContext` (single source of truth des types de
services). Annoter explicitement ici dupliquerait l'information et créerait
un second point de maintenance.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request

from config.constants import STATIC_DIR, VERSION

from .di import AppContext
from .middlewares import _setup_middlewares
from .warmup import lifespan


def build_app() -> FastAPI:
    """Composition Root : crée l'application et attache le lifespan.

    L'initialisation réelle des services (``_ctx.initialize()``) est déléguée
    au ``lifespan`` (controllers/warmup.py) pour garantir un démarrage/arrêt
    propre (startup/shutdown events).
    """
    app = FastAPI(
        title="JARVIS Portable Edition",
        version=VERSION,
        lifespan=lifespan,
    )

    _setup_middlewares(app)

    # Montage propre des fichiers statiques (sécurité + cache gérés nativement).
    if STATIC_DIR.exists():
        from .static_cache import CachedStaticFiles
        app.mount("/static", CachedStaticFiles(directory=STATIC_DIR), name="static")

    return app


# ==============================================================================
# DÉPENDANCES FASTAPI (à utiliser avec ``Depends()`` dans les routeurs)
# ==============================================================================

def get_app_context(request: Request) -> AppContext:
    """Dépendance racine : contexte applicatif attaché par le lifespan."""
    return request.app.state.context


def get_inference_service(context: AppContext = Depends(get_app_context)):
    """Dépendance granulaire : service d'inférence (LLM)."""
    return context.inference


def get_memory_service(context: AppContext = Depends(get_app_context)):
    """Dépendance granulaire : service de mémoire (habitudes)."""
    return context.memory


def get_vector_service(context: AppContext = Depends(get_app_context)):
    """Dépendance granulaire : service vectoriel (RAG)."""
    return context.vector


def get_agents_registry(context: AppContext = Depends(get_app_context)):
    """Dépendance granulaire : registre des 5 agents."""
    return context.agents


def get_orchestrator(context: AppContext = Depends(get_app_context)):
    """Dépendance granulaire : orchestrateur (AgentGraph)."""
    return context.orchestrator


__all__ = [
    "build_app",
    "get_app_context",
    "get_inference_service",
    "get_memory_service",
    "get_vector_service",
    "get_agents_registry",
    "get_orchestrator",
]
