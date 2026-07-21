"""Router FastAPI — Point d'entrée principal, monte les sous-routeurs.

Ce module agit comme le Composition Root de l'application FastAPI.
Il assemble les dépendances, enregistre les routeurs et expose l'app.
"""
import asyncio
import os
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from config.constants import PROJECT_DIR
from controllers.static_cache import serve_cached_file
from controllers.context import (
    REFRESH_INTERVAL, _check_ollama, _refresh_status_cache, build_app, cache_lock,
    status_cache, get_context,  # LEGACY: get_context doit être remplacé par l'injection via app.state
)
from controllers.routes import agents as agents_routes
from controllers.routes import analytics as analytics_routes
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
from controllers.routes import beta_dashboard as beta_dashboard_routes
from controllers.responses import ok
from services.profiling import get_slow_endpoints

STATIC_DIR = os.path.join(PROJECT_DIR, "static")


def create_app():
    """Factory de création de l'application FastAPI (Composition Root)."""
    app = build_app()

    # Enregistrement des routeurs métier
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

    # Beta dashboard (opt-in)
    if os.environ.get('JARVIS_BETA_DASHBOARD') == '1':
        app.include_router(beta_dashboard_routes.router)

    # --- Routes système inline (à extraire vers controllers/routes/system.py idéalement) ---

    @app.get("/api/backend")
    async def get_backend():
        return {"backend": "ollama"}

    @app.get("/api/models")
    async def list_models():
        # LEGACY: Remplacer par Depends() ou request.app.state.context après refonte de context.py
        context = get_context()
        inference = context.inference
        if inference is None:
            return {"models": [], "available": False, "error": "Backend inferieur non initialise."}
        
        # Offload de l'I/O bloquant vers un thread pour ne pas geler l'event loop
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
    async def get_status():
        context = get_context()
        
        with cache_lock:
            data = status_cache["data"] if time.time() - status_cache["ts"] < REFRESH_INTERVAL else None
        
        if data is None:
            # Offload des appels réseau bloquants
            ollama_status = await asyncio.to_thread(_check_ollama)
            await asyncio.to_thread(_refresh_status_cache, context, cache_lock, ollama_status)
            with cache_lock:
                data = status_cache["data"]
        
        data = dict(data)
        data["slow_endpoints"] = get_slow_endpoints()
        return ok(data)

    @app.get("/api/metrics")
    async def get_metrics():
        context = get_context()
        return ok(context.metrics.get_metrics())

    @app.get("/{path:path}")
    async def serve_static(path: str, request: Request):
        full_path = os.path.join(STATIC_DIR, path)
        resolved = os.path.abspath(full_path)
        static_root = os.path.abspath(STATIC_DIR)
        
        # Protection contre le path traversal
        if not (resolved == static_root or resolved.startswith(static_root + os.sep)):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        
        if os.path.isfile(resolved):
            return await asyncio.to_thread(serve_cached_file, resolved, request)
        
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    return app


# Exposition pour uvicorn
app = create_app()
