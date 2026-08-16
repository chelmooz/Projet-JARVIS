"""Service d'évaluation cyber multi-agents (implémente CyberEvalPort)."""

from __future__ import annotations

from typing import Any

from agents.revision import run_pipeline_with_revision


class CyberEvalService:
    """Implémentation du port CyberEvalPort.

    Réutilise le pipeline L6 (judge→advocate→evaluator + boucle revise).
    """

    def analyze(self, question: str, max_revisions: int = 2) -> dict[str, Any]:
        """Évalue la question et retourne une réponse simplifiée."""
        result, revisions = run_pipeline_with_revision(question, max_revisions=max_revisions)

        if result is None:
            return {
                "decision": "reject",
                "score": 0.0,
                "reasoning": "Pipeline échoué",
                "revisions": 0,
            }

        _judge, _advocate, evaluator = result

        return {
            "decision": evaluator.decision,
            "score": evaluator.final_score,
            "reasoning": evaluator.reasoning,
            "revisions": revisions,
        }
