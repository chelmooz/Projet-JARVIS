"""Contrats Pydantic des agents d'évaluation (extraits de ref-rag, Lot 12).

Modèles de sortie structurée uniquement — aucune logique d'agent, aucun
fallback : ``JudgeOutput`` (juge), ``AdvocateOutput`` (avocat du diable),
``EvaluatorOutput`` (synthèse finale). Autonome par design : il ne dépend
d'aucun autre module JARVIS, pour un parsing fiable côté LLM.
"""

from typing import Literal

from pydantic import BaseModel, Field


class JudgeOutput(BaseModel):
    """Sortie structurée du Juge (judge_output_v1)."""

    score: float = Field(ge=0.0, le=1.0)
    critique: str = Field(min_length=1)
    checks_passed: list[Literal["factualite", "coherence", "couverture", "style"]] = Field(default_factory=list)
    flags: list[Literal["hallucination_suspect", "omission_source", "contradiction_interne"]] = Field(
        default_factory=list
    )
    confidence: float = Field(ge=0.0, le=1.0)


class AdvocateOutput(BaseModel):
    """Sortie structurée de l'Avocat du diable (advocate_output_v1)."""

    score: float = Field(ge=0.0, le=1.0)
    faille: str
    claims_contested: list[str] = Field(default_factory=list)
    hallucination_risk: Literal["low", "medium", "high"] = "low"
    missing_context: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class EvaluatorOutput(BaseModel):
    """Décision finale de l'Évaluateur (evaluator_output_v1)."""

    decision: Literal["publish", "revise", "reject"]
    final_score: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1)
    revision_instructions: str | None = None
    verified_tier: Literal["machine-confirmed", "unverified"] = "unverified"
    confidence: float = Field(ge=0.0, le=1.0)
