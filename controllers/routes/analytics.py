"""Routes Analytics — Statistiques d'usage et pics.

Dettes signalées (non corrigées ici) :
- Les endpoints retournent des structures ad hoc (``get_stats()``, ``{peak_usage}``,
  ``{workflows, count}``) non enveloppées dans la convention ``{data, error}`` :
  le frontend attend ces formes plates. À trancher avec le contrat frontend.
- ``list_cyber_workflows`` (``/api/cyber/workflows``) est dans ce module
  ``analytics`` alors qu'il relève du domaine cyber (SRP / cohésion) — à
  déplacer vers ``controllers/routes/cyber.py`` (nécessite de monter le nouveau
  router dans ``router.py``).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from config.paths import CYBER_WORKFLOWS_CONFIG
from controllers.context import get_app_context
from controllers.di import AppContext

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/analytics")
async def get_analytics(context: AppContext = Depends(get_app_context)):
    """Statistiques d'usage (en mémoire, lock interne → safe en async)."""
    return context.analytics.get_stats()


@router.get("/api/analytics/peak")
async def get_peak(context: AppContext = Depends(get_app_context)):
    """Pic d'usage (modèle/agent le plus utilisé)."""
    return {"peak_usage": context.analytics.get_most_used()}


@router.get("/api/cyber/workflows")
def list_cyber_workflows():
    """Liste les workflows cyber (I/O bloquant → threadpool FastAPI)."""
    try:
        with open(CYBER_WORKFLOWS_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        _logger.warning("cyber_workflows.json illisible/absent: %s", e)
        return JSONResponse({"error": "Workflows non trouvés", "workflows": {}}, status_code=404)
    workflows = data.get("workflows", {})
    return {"workflows": workflows, "count": len(workflows)}


__all__ = ["router"]
