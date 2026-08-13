"""Helpers du moteur de pipelines — fonctions pures.

Extraites de ``PipelineService`` (découpage Phase 20) : détection de
stagnation, reformulation HyDE, analyse d'erreurs et construction des
réponses d'échec sont des fonctions pures, testables isolément.
"""

from __future__ import annotations

from typing import Any


def is_stagnant(current_reason: str, last_reason: str, attempt: int) -> bool:
    """Détection de stagnation : même reason que la tentative précédente."""
    return attempt > 0 and current_reason == last_reason


def build_hyde_query(original_task: str, previous_response: str) -> str:
    """Reformulation HyDE : enrichit la requête avec la réponse précédente."""
    return (
        f"{original_task}\n\n"
        f"Contexte de la tentative précédente : {previous_response}\n\n"
        f"Affine et précise le diagnostic."
    )


def has_fatal_error(results: list[dict[str, Any]]) -> bool:
    """Vérifie si la dernière étape a échoué de manière fatale."""
    if not results:
        return False
    last = results[-1]
    return last.get("error") is not None


def build_failure(pipeline_id: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Construit le dict de réponse en cas d'échec."""
    last_error = results[-1].get("error", "Erreur inconnue")
    return {
        "pipeline": pipeline_id,
        "steps": len(results),
        "results": results,
        "error": last_error,
    }
