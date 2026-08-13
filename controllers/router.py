"""Router FastAPI — Point d'entrée principal, monte les sous-routeurs.

Ce module agit comme le Composition Root de l'application FastAPI.
Il assemble les dépendances, enregistre les routeurs et expose l'app.

Dettes signalées (non corrigées ici) :
- Les routes système inline (``/``, ``/api/status``, ``/api/backend``,
  ``/api/models``, ``/api/metrics``, ``/{path:path}``) devraient être extraites
  vers ``controllers/routes/system.py`` (SRP : le router monte les routeurs,
  il ne définit pas d'endpoints).
- La structure du dict de status (``_build_status``) est une réimplémentation
  suite à la suppression des globales legacy de l'ancien ``context.py`` ; à
  valider contre le contrat attendu par le frontend (static/).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from config.constants import REFRESH_INTERVAL
from config.paths import STATIC_DIR
from controllers.context import _ctx, build_app
from controllers.responses import Envelope, ok
from controllers.static_cache import serve_cached_file
from controllers.status import build_status
from services.profiling import get_slow_endpoints

_logger = logging.getLogger(__name__)


def _get_context(request: Request) -> Any:
    """Retourne le contexte applicatif de la requête.

    Utilise ``app.state.context`` (posé par le ``lifespan``, cf.
    ``controllers/warmup.py``) une fois l'application démarrée. En dehors du
    cycle de vie complet de l'app (ex. ``TestClient`` instancié sans
    ``with``, tests qui construisent l'app sans déclencher le lifespan), on
    retombe sur le singleton de compatibilité ``controllers.context._ctx``
    afin que les fixtures de test qui le mutent directement restent prises
    en compte.
    """
    context = getattr(request.app.state, "context", None)
    if context is not None:
        return context
    from controllers.context import _ctx

    return _ctx


def _mount_router(app: FastAPI, router: Any) -> None:
    """Monte un sous-routeur directement dans la liste des routes de l'app.

    Équivalent fonctionnel à ``app.include_router(router)`` pour nos besoins :
    aucun de nos sous-routeurs n'utilise ``prefix``/``dependencies`` au
    niveau du routeur (les éventuels ``tags`` sont déjà portés par les routes
    elles-mêmes, cf. ``controllers/routes/settings.py``).

    Contourne volontairement ``include_router`` : les versions récentes de
    FastAPI enveloppent chaque routeur inclus dans un objet interne
    paresseux (``_IncludedRouter``) qui casse l'introspection directe de
    ``app.routes`` (utilisée par ``scripts/check_api_contract.py`` pour la
    détection de drift front/back). Étendre directement la liste conserve
    des ``APIRoute`` réels : dispatch identique, mais introspectables.
    """
    app.router.routes.extend(router.routes)


async def get_backend() -> dict[str, str]:
    return {"backend": "ollama"}


async def get_metrics(request: Request) -> Envelope:
    context = _get_context(request)
    return ok(context.metrics.get_metrics())


def list_models(request: Request) -> dict[str, Any]:
    """Liste les modèles disponibles (reste sync : appel réseau Ollama bloquant)."""
    context = _get_context(request)
    inference = getattr(context, "inference", None)
    if inference is None:
        return {"models": [], "available": False, "error": "Backend inférence non initialisé."}
    models = inference.list_models()
    return {"models": models, "available": True}


def index(request: Request) -> Any:
    """Sert la page d'accueil (reste sync : lecture disque statique)."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    resp = serve_cached_file(index_path, request)
    if resp is not None:
        return resp
    return {"message": "JARVIS API — voir /docs pour la documentation"}


async def get_status(request: Request) -> Envelope:
    """Renvoie le status agrégé (async : utilise asyncio.Lock pour ne pas bloquer l'event loop)."""
    context = _get_context(request)
    cache = request.app.state.status_cache
    lock = request.app.state.status_lock
    async with lock:
        data = cache["data"] if time.time() - cache["ts"] < REFRESH_INTERVAL else None
    if data is None:
        status = build_status(context)
        async with lock:
            cache["data"] = status
            cache["ts"] = time.time()
            data = status
    data = dict(data)
    data["slow_endpoints"] = get_slow_endpoints()
    return ok(data)


def serve_static(path: str, request: Request) -> Any:
    """Sert les fichiers statiques avec protection path traversal.

    Reste sync (module-level) : lecture disque statique.
    """
    full_path = os.path.join(STATIC_DIR, path)
    resolved = os.path.abspath(full_path)
    static_root = os.path.abspath(STATIC_DIR)
    if not (resolved == static_root or resolved.startswith(static_root + os.sep)):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if os.path.isfile(resolved):
        resp = serve_cached_file(resolved, request)
        if resp is not None:
            return resp
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


def create_app() -> FastAPI:
    """Factory de création de l'application FastAPI (Composition Root)."""
    app = build_app()

    # Contexte applicatif exposé dès la création (pas seulement au lifespan) :
    # `get_app_context`/`Depends(get_app_context)` et les tests qui manipulent
    # directement le singleton `_ctx` (sans déclencher le lifespan, ex.
    # `TestClient(app)` sans `with`) doivent trouver un contexte valide.
    # Le lifespan (`controllers/warmup.py`) ne réassigne rien si déjà présent.
    app.state.context = _ctx

    # Cache de status attaché à l'app (pas de globale mutable).
    app.state.status_cache = {"data": None, "ts": 0.0}
    app.state.status_lock = asyncio.Lock()

    # Middleware d'authentification token mono-user
    @app.middleware("http")
    async def verify_token_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Skip token verification for health checks and docs
        if (
            request.url.path in ["/", "/api/status", "/api/backend", "/api/metrics"]
            or request.url.path.startswith("/docs")
            or request.url.path.startswith("/redoc")
            or request.url.path.startswith("/openapi.json")
        ):
            return await call_next(request)

        # Skip token verification if OpenWebUI is disabled (no CORS needed either)
        if os.environ.get("JARVIS_ENABLE_OPENWEBUI", "0") != "1":
            return await call_next(request)

        # Require token in header for all other routes
        token = request.headers.get("X-JARVIS-Token")
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Missing X-JARVIS-Token header"})

        # Verify token
        token_file = Path(__file__).resolve().parent.parent / "memory" / ".jarvis_token"
        if not token_file.exists():
            return JSONResponse(status_code=503, content={"detail": "Authentication token not available"})

        valid_token = token_file.read_text().strip()
        if token != valid_token:
            return JSONResponse(status_code=401, content={"detail": "Invalid X-JARVIS-Token"})

        return await call_next(request)

    # Lazy import des sous-routeurs (désenchevêtrement 15.8)
    from controllers.routes import agents as agents_routes
    from controllers.routes import analytics as analytics_routes
    from controllers.routes import beta_dashboard as beta_dashboard_routes
    from controllers.routes import code_review as code_review_routes
    from controllers.routes import conversations as conv_routes
    from controllers.routes import diagnostic as diagnostic_routes
    from controllers.routes import diagnostic_ext as diagnostic_ext_routes
    from controllers.routes import documents as doc_routes
    from controllers.routes import files as files_routes
    from controllers.routes import jarvis as jarvis_routes
    from controllers.routes import kill_coding as kill_coding_routes
    from controllers.routes import pipelines as pipelines_routes
    from controllers.routes import quality_audit as quality_audit_routes
    from controllers.routes import settings as settings_routes
    from controllers.routes import skills as skills_routes

    # Enregistrement des routeurs métier.
    for sub_router in (
        jarvis_routes.router,
        agents_routes.router,
        conv_routes.router,
        diagnostic_routes.router,
        diagnostic_ext_routes.router,
        doc_routes.router,
        analytics_routes.router,
        files_routes.router,
        pipelines_routes.router,
        code_review_routes.router,
        kill_coding_routes.router,
        quality_audit_routes.router,
        settings_routes.router,
        skills_routes.router,
    ):
        _mount_router(app, sub_router)

    # Beta dashboard (opt-in).
    if os.environ.get("JARVIS_BETA_DASHBOARD") == "1":
        _mount_router(app, beta_dashboard_routes.router)

    # Routes système (extraites vers routes/system.py pour SRP)
    from controllers.routes import system as system_routes

    _mount_router(app, system_routes.router)

    # Routes système inline (dette : à extraire vers routes/system.py)
    app.get("/api/backend")(get_backend)
    app.get("/api/models")(list_models)
    app.get("/", response_model=None)(index)
    app.get("/api/status")(get_status)
    app.get("/api/metrics")(get_metrics)
    # Enregistrement de la fonction module-level (plus de closure)
    app.get("/{path:path}", response_model=None)(serve_static)

    return app


# Exposition pour uvicorn.
app = create_app()


__all__ = ["create_app", "app"]
