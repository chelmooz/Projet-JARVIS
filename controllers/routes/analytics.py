"""Routes Analytics — Statistiques d'usage et pics."""
import json
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from config.paths import CYBER_WORKFLOWS_CONFIG

_logger = logging.getLogger("jarvis.routes.analytics")

router = APIRouter()


def _analytics():
    from controllers.context import analytics
    return analytics


@router.get("/api/analytics")
async def get_analytics():
    # Stats en mémoire (lock interne) : safe en async.
    return _analytics().get_stats()


@router.get("/api/analytics/peak")
async def get_peak():
    # Stats en mémoire (lock interne) : safe en async.
    return {"peak_usage": _analytics().get_most_used()}


@router.get("/api/cyber/workflows")
def list_cyber_workflows():
    # Laisse sync : lit le fichier config/cyber_workflows.json (I/O bloquant).
    try:
        with open(CYBER_WORKFLOWS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        workflows = data.get("workflows", {})
        return {"workflows": workflows, "count": len(workflows)}
    except Exception as e:
        _logger.debug("cyber_workflows.json illisible/absent: %s", e)
        return JSONResponse({"error": "Workflows non trouves", "workflows": {}}, status_code=404)
