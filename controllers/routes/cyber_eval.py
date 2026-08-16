"""Route API pour l'évaluation cyber multi-agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from services.cyber_eval_service import CyberEvalService

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """Requête pour l'évaluation cyber."""

    question: str = Field(..., min_length=1, description="Question à évaluer")
    max_revisions: int = Field(default=2, ge=0, le=10, description="Nombre max de révisions")


_service: CyberEvalService | None = None


def get_cyber_eval_service() -> CyberEvalService:
    """Singleton du service (lazy init au premier appel)."""
    global _service
    if _service is None:
        from services.cyber_eval_service import CyberEvalService

        _service = CyberEvalService()
    return _service


@router.post("/api/cyber/analyze")
async def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    """Évalue une question via le pipeline multi-agents judge→advocate→evaluator."""
    return get_cyber_eval_service().analyze(req.question, max_revisions=req.max_revisions)


__all__ = ["router"]
