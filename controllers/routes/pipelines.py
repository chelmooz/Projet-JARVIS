"""Routes Pipelines — Lister et exécuter des pipelines."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from controllers.context import get_app_context
from controllers.di import AppContext
from controllers.responses import fail, ok
from models.schemas import PipelineRunRequest
from services.pipeline import PipelineError

router = APIRouter()


@router.get("/api/pipelines")
async def list_pipelines(context: AppContext = Depends(get_app_context)):
    """Liste les pipelines enregistrés (en mémoire, safe en async)."""
    pipeline = context.pipeline
    if pipeline is None:
        return ok({"pipelines": []})
    return ok({"pipelines": pipeline.list()})


@router.post("/api/pipelines/run")
def run_pipeline(
    body: PipelineRunRequest,
    context: AppContext = Depends(get_app_context),
):
    """Exécute un pipeline par son ID."""
    pipeline = context.pipeline
    if pipeline is None:
        return fail("Pipeline service non initialisé", status_code=503)
    metrics = context.metrics
    if metrics is not None:
        metrics.incr_pipeline_run()
    try:
        result = pipeline.run(body.pipeline_id, body.task, body.context)
    except PipelineError as e:
        return fail(str(e), status_code=404)
    return ok(result)


__all__ = ["router"]
