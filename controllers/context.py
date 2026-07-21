"""Context & Dependency Injection — Point d'assemblage propre de l'application.

Refacto SOLID / FastAPI Best Practices :
- Suppression totale des variables globales mutables (legacy).
- Injection de dépendances via `request.app.state.context`.
- Responsabilité unique : fournir des dépendances typées aux contrôleurs.
"""
from __future__ import annotations

import types
from typing import Any

from fastapi import Depends, FastAPI, Request

from config.constants import VERSION
from config.paths import STATIC_DIR
from controllers.di import AppContext
from controllers.middlewares import _setup_middlewares
from controllers.warmup import lifespan


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
# STUBS LEGACY POUR COMPATIBILITÉ DES TESTS (NE PAS UTILISER EN PRODUCTION)
# ==============================================================================
def _check_ollama() -> bool:
    """Stub pour test_wave_a.py — vérifie si Ollama répond."""
    try:
        from services.inference import InferenceService
        return InferenceService().ping()
    except Exception:
        return False


def _ctx() -> types.SimpleNamespace:
    """Stub pour test_api.py / test_response_wrapper.py — retourne un contexte minimal."""
    ctx = types.SimpleNamespace()
    ctx.orchestrator = None
    ctx.analytics = None
    ctx.conversations = None
    ctx.inference = None
    ctx.vector = None
    ctx.memory = None
    ctx.log = None
    ctx.metrics = None
    ctx.agents = {}
    return ctx


def _sync_module_globals(context: Any = None) -> None:
    """Stub no-op pour test_api.py / test_response_wrapper.py.
    
    Anciennement : synchronisait les globales de module (analytics, conversations, etc.)
    depuis le contexte. Supprimé lors du refacto (injection via app.state).
    Conservé comme no-op pour ne pas casser la collection des tests legacy.
    """
    pass


__all__ = [
    "build_app",
    "get_app_context",
    "get_inference_service",
    "get_memory_service",
    "get_vector_service",
    "get_agents_registry",
    "get_orchestrator",
    "_check_ollama",
    "_ctx",
    "_sync_module_globals",
]
