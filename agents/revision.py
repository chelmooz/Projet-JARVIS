"""Boucle de révision : relance le pipeline si l'évaluateur décide 'revise'."""

from __future__ import annotations

from agents.eval_contracts import AdvocateOutput, EvaluatorOutput, JudgeOutput
from agents.orchestrator import run_pipeline


def run_pipeline_with_revision(
    question: str, max_revisions: int = 2
) -> tuple[JudgeOutput, AdvocateOutput, EvaluatorOutput] | None:
    """Exécute le pipeline avec révisions automatiques si ``decision == 'revise'``.

    Retourne la dernière exécution réussie, ou ``None`` si toutes échouent.
    """
    current_question = question
    revisions_left = max_revisions

    while True:
        result = run_pipeline(current_question)
        if result is None:
            return None

        judge, advocate, evaluator = result

        # Pas de révision demandée ou budget épuisé → retourner
        if evaluator.decision != "revise" or revisions_left <= 0:
            return result

        # Construire question enrichie pour la révision
        current_question = question + "\n\n[Instructions de révision]:\n" + (evaluator.revision_instructions or "")
        revisions_left -= 1
