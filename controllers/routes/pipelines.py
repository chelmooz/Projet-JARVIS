"""Routes Pipelines — Lister et exécuter des pipelines."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models.schemas import PipelineRunRequest
from services.pipeline import PipelineError, PipelineService

router = APIRouter()

_engine: PipelineService | None = None


def get_engine() -> PipelineService:
    global _engine
    if _engine is None:
        from controllers.context import inference, memory
        _engine = PipelineService(inference=inference, memory=memory)
    return _engine


@router.get("/api/pipelines")
async def list_pipelines():
    # list() lit les pipelines en mémoire : safe en async.
    return {"pipelines": get_engine().list()}


@router.post("/api/pipelines/run")
def run_pipeline(body: PipelineRunRequest):
    from controllers.context import metrics
    metrics.incr_pipeline_run()
    eng = get_engine()
    try:
        result = eng.run(body.pipeline_id, body.task, body.context)
    except PipelineError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    return result
