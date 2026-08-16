"""Boucle de révision : relance le pipeline si l'évaluateur décide 'revise'."""

from __future__ import annotations

from agents.eval_contracts import AdvocateOutput, EvaluatorOutput, JudgeOutput
from agents.orchestrator import run_pipeline


def run_pipeline_with_revision(
    question: str, max_revisions: int = 2
) -> tuple[tuple[JudgeOutput, AdvocateOutput, EvaluatorOutput] | None, int]:
    """Exécute le pipeline avec révisions automatiques si ``decision == 'revise'``.

    Retourne ``(résultat, revisions_count)`` : la dernière exécution réussie
    (ou ``None`` si toutes échouent) et le nombre de tours de révision effectués.
    """
    current_question = question
    revisions_left = max_revisions
    revisions_done = 0

    while True:
        result = run_pipeline(current_question)
        if result is None:
            return None, revisions_done

        judge, advocate, evaluator = result

        # Pas de révision demandée ou budget épuisé → retourner
        if evaluator.decision != "revise" or revisions_left <= 0:
            return result, revisions_done

        # Construire question enrichie pour la révision
        current_question = question + "\n\n[Instructions de révision]:\n" + (evaluator.revision_instructions or "")
        revisions_left -= 1
        revisions_done += 1
