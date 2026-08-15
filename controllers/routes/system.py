"""Routes système — Endpoints de monitoring et de configuration."""

from __future__ import annotations

import asyncio
import time
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from controllers.router import _get_context

from services.static_files import serve_static_file

_logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# Health Check
# =============================================================================

@router.get("/api/health")
async def health(request: Request) -> JSONResponse:
    """Endpoint de santé pour le monitoring."""
    context = _get_context(request)
    inference = getattr(context, "inference", None)
    ollama_up = False
    if inference is not None and hasattr(inference, "ping"):
        try:
            ollama_up = bool(inference.ping())
        except Exception:
            _logger.warning("Inference ping failed", exc_info=True)

    return JSONResponse(content={"ollama": ollama_up, "version": "6.0"}, status_code=200 if ollama_up else 503)


# =============================================================================
# System Information
# =============================================================================

@router.get("/api/backend")
async def get_backend() -> JSONResponse:
    """Retourne le backend utilisé."""
    return JSONResponse(content={"backend": "ollama"}, status_code=200)


@router.get("/api/models")
async def list_models(request: Request) -> JSONResponse:
    """Liste les modèles disponibles."""
    context = _get_context(request)
    inference = getattr(context, "inference", None)
    if inference is None:
        return JSONResponse(content={"models": [], "available": False}, status_code=200)
    models = inference.list_models()
    return JSONResponse(content={"models": models, "available": True}, status_code=200)


@router.get("/", response_model=None)
async def index(request: Request) -> JSONResponse:
    """Sert la page d'accueil."""
    return JSONResponse(content={"message": "JARVIS API — voir /docs pour la documentation"})


@router.get("/api/status")
async def get_status(request: Request) -> JSONResponse:
    """Renvoie le status agrégé."""
    context = _get_context(request)
    cache = request.app.state.status_cache
    lock = request.app.state.status_lock

    async with lock:
        data = cache["data"] if time.time() - cache["ts"] < 60 else None
    if data is None:
        from controllers.status import build_status
        async with lock:
            cache["data"] = build_status(context)
            cache["ts"] = time.time()
        data = cache["data"]
    data = dict(data)
    if not data:
        return JSONResponse(content={"error": "no data"}, status_code=404)
    return JSONResponse(content=data, status_code=200)


@router.get("/api/metrics")
async def get_metrics(request: Request) -> JSONResponse:
    """Retourne les métriques de l'application."""
    context = _get_context(request)
    inference = getattr(context, "inference", None)
    models = inference.list_models() if inference else []
    return JSONResponse(content={"models": models, "status": "ok"}, status_code=200)


# =============================================================================
# Static Files
# =============================================================================

@router.get("/static/{path:path}")
async def serve_static(path: str, request: Request) -> JSONResponse:
    """Sert les fichiers statiques."""
    return await serve_static_file(request, path)