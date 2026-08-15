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

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from controllers.router import _get_context
from controllers.status import build_status
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
# Static Files
# =============================================================================


@router.get("/static/{path:path}")
async def serve_static(path: str, request: Request) -> Response:
    """Sert les fichiers statiques."""
    return serve_static_file(request, path)
