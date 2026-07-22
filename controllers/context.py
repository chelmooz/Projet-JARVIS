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
def get_context() -> types.SimpleNamespace:
    """Stub pour test_context_refactor.py — retourne le contexte singleton.

    Anciennement : retournait un contexte global mutable neuf à chaque appel.
    Retourne désormais le singleton module-level `_ctx` (objet partagé) pour que
    les `monkeypatch.setattr(ctx_mod._ctx, ...)` des tests posent l'attribut sur
    un objet stable et soient restaurés proprement au teardown.
    """
    return _ctx


def _check_ollama() -> bool:
    """Stub pour test_wave_a.py — vérifie si Ollama répond."""
    try:
        from services.inference import InferenceService
        return InferenceService().ping()
    except Exception:
        return False


class _CtxStub(types.SimpleNamespace):
    """Singleton module-level remplaçant l'ancienne fonction-piège `_ctx()`.

    Ce n'est PLUS une fonction : c'est un OBJET partagé au niveau module.
    Les tests qui font `monkeypatch.setattr(ctx_mod._ctx, "x", fake)` posent
    l'attribut sur cet objet (pas sur un objet fonction) et monkeypatch le
    restaure proprement au teardown → plus de pollution module-level dépendante
    de l'ordre d'exécution.

    Reste callable (`_ctx()` retourne `self`) pour ne casser aucun appel legacy
    éventuel, mais l'usage nominal est l'accès d'attribut direct (`_ctx.vector`).
    """

    def __call__(self) -> "_CtxStub":
        return self

    def initialize(self) -> None:
        """No-op qui remet les attributs à None (nettoie les fakes des tests).

        Dans le contexte de test, cette méthode est appelée au teardown pour
        nettoyer les fakes (FakeInference, FakeMemory, etc.) et éviter la
        pollution inter-tests. Elle n'initialise PAS les vrais services (pas
        d'appels réseau), car _CtxStub est un stub pour les tests uniquement.
        """
        self.inference = None
        self.memory = None
        self.vector = None
        self.conversations = None
        self.agents = {}
        self.log = None
        self.analytics = None
        self.metrics = None
        self.router_svc = None
        self.orchestrator = None
        self._initialized = False

    @property
    def ready(self) -> bool:
        """Propriété qui retourne l'état d'initialisation (pour test_conversations_routes)."""
        return self._initialized


_ctx = _CtxStub(
    orchestrator=None,
    analytics=None,
    conversations=None,
    inference=None,
    vector=None,
    memory=None,
    log=None,
    metrics=None,
    agents={},
    router_svc=None,
    _initialized=False,
)


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
    "get_context",
    "_check_ollama",
    "_ctx",
    "_sync_module_globals",
]