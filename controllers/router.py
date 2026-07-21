"""Router FastAPI — Point d'entrée principal, monte les sous-routeurs.

Ce module agit comme le Composition Root de l'application FastAPI.
Il assemble les dépendances, enregistre les routeurs et expose l'app.

Dettes signalées (non corrigées ici) :
- Les routes système inline (``/``, ``/api/status``, ``/api/backend``,
  ``/api/models``, ``/api/metrics``, ``/{path:path}``) devraient être extraites
  vers ``controllers/routes/system.py`` (SRP : le router monte les routeurs,
  il ne définit pas d'endpoints).
- La structure du dict de status (``_build_status``) est une réimplémentation
  suite à la suppression des globales legacy de ``context.py`` ; à valider
  contre le contrat attendu par le frontend (static/).
"""

from __future__ import annotations

import asyncio
import os
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config.constants import REFRESH_INTERVAL, VERSION
from config.paths import STATIC_DIR
from controllers.context import build_app
from controllers.responses import ok
from controllers.routes import agents as agents_routes
from controllers.routes import analytics as analytics_routes
from controllers.routes import beta_dashboard as beta_dashboard_routes
from controllers.routes import code_review as code_review_routes
from controllers.routes import conversations as conv_routes
from controllers.routes import diagnostic as diagnostic_routes
from controllers.routes import documents as doc_routes
from controllers.routes import files as files_routes
from controllers.routes import jarvis as jarvis_routes
from controllers.routes import kill_coding as kill_coding_routes
from controllers.routes import pipelines as pipelines_routes
from controllers.routes import quality_audit as quality_audit_routes
from controllers.routes import settings as settings_routes
from controllers.routes import skills as skills_routes
from controllers.static_cache import serve_cached_file
from services.profiling import get_slow_endpoints


def _service_healthy(service) -> bool:
    """État de santé défensif d'un service (``is_healthy()`` optionnel)."""
    check = getattr(service, "is_healthy", None)
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:
        return False


def _build_status(context) -> dict:
    """Construit le dict de status à partir du contexte (état des services).

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
            ollama_up = False
    return {
        "ollama": ollama_up,
        "inference": _service_healthy(inference),
        "vector": _service_healthy(getattr(context, "vector", None)),
        "memory": _service_healthy(getattr(context, "memory", None)),
        "conversations": _service_healthy(getattr(context, "conversations", None)),
        "version": VERSION,
    }


def create_app() -> FastAPI:
    """Factory de création de l'application FastAPI (Composition Root)."""
    app = build_app()

    # Cache de status attaché à l'app (pas de globale mutable).
    app.state.status_cache = {"data": None, "ts": 0.0}
    app.state.status_lock = threading.Lock()

    # Enregistrement des routeurs métier.
    app.include_router(jarvis_routes.router)
    app.include_router(agents_routes.router)
    app.include_router(conv_routes.router)
    app.include_router(diagnostic_routes.router)
    app.include_router(doc_routes.router)
    app.include_router(analytics_routes.router)
    app.include_router(files_routes.router)
    app.include_router(pipelines_routes.router)
    app.include_router(code_review_routes.router)
    app.include_router(kill_coding_routes.router)
    app.include_router(quality_audit_routes.router)
    app.include_router(settings_routes.router)
    app.include_router(skills_routes.router)

    # Beta dashboard (opt-in).
    if os.environ.get("JARVIS_BETA_DASHBOARD") == "1":
        app.include_router(beta_dashboard_routes.router)

    # --- Routes système inline (dette : à extraire vers routes/system.py) ---

    @app.get("/api/backend")
    async def get_backend():
        return {"backend": "ollama"}

    @app.get("/api/models")
    async def list_models(request: Request):
        context = request.app.state.context
        inference = getattr(context, "inference", None)
        if inference is None:
            return {"models": [], "available": False, "error": "Backend inférence non initialisé."}
        # Offload de l'I/O bloquant vers un thread pour ne pas geler l'event loop.
        models = await asyncio.to_thread(inference.list_models)
        return {"models": models, "available": True}

    @app.get("/")
    async def index(request: Request):
        index_path = os.path.join(STATIC_DIR, "index.html")
        resp = await asyncio.to_thread(serve_cached_file, index_path, request)
        if resp is not None:
            return resp
        return {"message": "JARVIS API — voir /docs pour la documentation"}

    @app.get("/api/status")
    async def get_status(request: Request):
        context = request.app.state.context
        cache = request.app.state.status_cache
        lock = request.app.state.status_lock
        with lock:
            data = cache["data"] if time.time() - cache["ts"] < REFRESH_INTERVAL else None
        if data is None:
            status = await asyncio.to_thread(_build_status, context)
            with lock:
                cache["data"] = status
                cache["ts"] = time.time()
                data = status
        data = dict(data)
        data["slow_endpoints"] = get_slow_endpoints()
        return ok(data)

    @app.get("/api/metrics")
    async def get_metrics(request: Request):
        context = request.app.state.context
        return ok(context.metrics.get_metrics())

    @app.get("/{path:path}")
    async def serve_static(path: str, request: Request):
        full_path = os.path.join(STATIC_DIR, path)
        resolved = os.path.abspath(full_path)
        static_root = os.path.abspath(STATIC_DIR)
        # Protection contre le path traversal.
        if not (resolved == static_root or resolved.startswith(static_root + os.sep)):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if os.path.isfile(resolved):
            resp = await asyncio.to_thread(serve_cached_file, resolved, request)
            if resp is not None:
                return resp
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    return app


# Exposition pour uvicorn.
app = create_app()


__all__ = ["create_app", "app"]
