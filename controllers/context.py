"""Context & Dependency Injection — Point d'assemblage propre de l'application.

Refacto SOLID / FastAPI Best Practices :
- Suppression totale des variables globales mutables (legacy).
- Injection de dépendances via `request.app.state.context`.
- Responsabilité unique : fournir des dépendances typées aux contrôleurs.
"""
import logging
import os

from fastapi import FastAPI, Request

from config.constants import VERSION, STATIC_DIR
from controllers.di import AppContext
from controllers.middlewares import _setup_middlewares
from controllers.warmup import lifespan

_logger = logging.getLogger("jarvis.context")


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
    if STATIC_DIR and os.path.exists(STATIC_DIR):
        from controllers.static_cache import CachedStaticFiles
        app.mount("/static", CachedStaticFiles(directory=STATIC_DIR), name="static")
        
    return app


# ==============================================================================
# DÉPENDANCES FASTAPI (À utiliser avec `Depends()` dans les routeurs)
# ==============================================================================

def get_app_context(request: Request) -> AppContext:
    """Dépendance principale : retourne le contexte de l'application."""
    # Le lifespan de l'app est responsable d'initialiser et d'attacher ceci à app.state
    return request.app.state.context


# Helpers pour une injection granulaire (recommandé pour le TDD et la clarté)
# Exemple d'usage dans une route : 
# def my_route(inf: InferenceService = Depends(get_inference_service)):

def get_inference_service(context: AppContext = Depends(get_app_context)):
    return context.inference

def get_memory_service(context: AppContext = Depends(get_app_context)):
    return context.memory

def get_vector_service(context: AppContext = Depends(get_app_context)):
    return context.vector

def get_agents_registry(context: AppContext = Depends(get_app_context)):
    return context.agents

def get_orchestrator(context: AppContext = Depends(get_app_context)):
    return context.orchestrator
