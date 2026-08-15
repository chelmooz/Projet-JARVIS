"""Routes système — Endpoints de monitoring et de configuration.

Dette signalée : ``get_backend``, ``list_models``, ``index``, ``get_status``,
``get_metrics`` avaient été dupliqués ici par-dessus les implémentations
inline de ``controllers/router.py`` (encore la source unique, correcte —
enveloppe ``{data, error}`` via ``controllers.responses.ok``). Comme
``system_routes`` est monté avant l'enregistrement des routes inline,
ces doublons interceptaient les requêtes en premier et servaient un
format de réponse différent (non enveloppé) — cause des échecs
``test_api_health.py::test_status_*``. Retirés : seuls ``health`` (unique
à ce module, corrigé ci-dessous) et ``serve_static`` restent ici.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.responses import Response

from controllers.router import _get_context
from controllers.status import build_status
from services.profiling import get_slow_endpoints
from services.static_files import serve_static_file

_logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# Health Check
# =============================================================================


@router.get("/api/health")
async def health(request: Request) -> JSONResponse:
    """Endpoint de santé pour le monitoring — agrège l'état de tous les services.

    Réutilise ``build_status`` (source unique de l'état des services, déjà
    utilisée par ``/api/status``) plutôt que de dupliquer la logique de
    healthcheck.
    """
    context = _get_context(request)
    data = build_status(context)
    healthy = all(data[key] for key in ("inference", "vector", "memory", "conversations"))
    return JSONResponse(content={"healthy": healthy}, status_code=200 if healthy else 503)


# =============================================================================
# Status Stream — SSE (remplace le polling côté client)
# =============================================================================


async def _status_events(request: Request, heartbeat_every: int = 15, max_duration: int = 60) -> AsyncIterator[dict[str, Any]]:
    """Flux SSE : statut courant puis heartbeats jusqu'à déconnexion ou ``max_duration``.

    Le client SSE (EventSource, cf. status.js) se reconnecte automatiquement
    (``retry: 5000``) — pas besoin de garder la connexion ouverte indéfiniment.
    """
    context = _get_context(request)
    cache = request.app.state.status_cache
    lock = request.app.state.status_lock

    async with lock:
        data = dict(cache["data"]) if cache["data"] else build_status(context)
    data["slow_endpoints"] = get_slow_endpoints()
    yield {"data": json.dumps(data)}

    elapsed = 0
    while elapsed < max_duration and not await request.is_disconnected():
        await asyncio.sleep(heartbeat_every)
        elapsed += heartbeat_every
        yield {"comment": "keep"}


@router.get("/api/status/stream")
async def status_stream(request: Request) -> EventSourceResponse:
    """Endpoint SSE consommé par le panneau latéral (status.js: connectStatusSSE)."""
    return EventSourceResponse(_status_events(request), headers={"retry": "5000"})


# =============================================================================
# Static Files
# =============================================================================


@router.get("/static/{path:path}")
async def serve_static(path: str, request: Request) -> Response:
    """Sert les fichiers statiques."""
    return serve_static_file(request, path)
