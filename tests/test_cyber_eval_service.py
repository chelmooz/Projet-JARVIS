"""Tests du service CyberEval (``services/cyber_eval_service.py``).

``run_pipeline_with_revision`` est mocké — zéro appel Ollama réel.
"""

from unittest.mock import patch

from agents.eval_contracts import AdvocateOutput, EvaluatorOutput, JudgeOutput
from services.cyber_eval_service import CyberEvalService


def _tuple(decision: str, score: float = 0.85, reasoning: str = "OK"):
    judge = JudgeOutput(score=0.9, critique="Réponse correcte", confidence=0.8)
    advocate = AdvocateOutput(score=0.7, faille="Manque une source", confidence=0.7)
    evaluator = EvaluatorOutput(
        decision=decision,
        final_score=score,
        reasoning=reasoning,
        confidence=0.6,
    )
    return judge, advocate, evaluator


def test_analyze_returns_simplified_response():
    """Pipeline OK → réponse simplifiée avec score et reasoning."""
    with patch(
        "services.cyber_eval_service.run_pipeline_with_revision",
        return_value=(_tuple("publish", 0.85, "OK"), 0),
    ):
        result = CyberEvalService().analyze("question")
    assert result == {"decision": "publish", "score": 0.85, "reasoning": "OK", "revisions": 0}


def test_analyze_returns_reject_on_pipeline_failure():
    """Pipeline en échec → fail-closed reject."""
    with patch(
        "services.cyber_eval_service.run_pipeline_with_revision",
        return_value=(None, 0),
    ):
        result = CyberEvalService().analyze("question")
    assert result == {"decision": "reject", "score": 0.0, "reasoning": "Pipeline échoué", "revisions": 0}


def test_analyze_counts_revisions():
    """Le compteur de révisions renvoyé par L6 est propagé."""
    with patch(
        "services.cyber_eval_service.run_pipeline_with_revision",
        return_value=(_tuple("publish", 0.9, "Révisé"), 2),
    ):
        result = CyberEvalService().analyze("question")
    assert result["decision"] == "publish"
    assert result["revisions"] == 2


def test_analyze_uses_max_revisions_param():
    """max_revisions est transmis à L6."""
    with patch(
        "services.cyber_eval_service.run_pipeline_with_revision",
        return_value=(_tuple("publish"), 0),
    ) as mock_pipeline:
        CyberEvalService().analyze("question", max_revisions=1)
    mock_pipeline.assert_called_once_with("question", max_revisions=1)


def test_analyze_default_max_revisions_is_2():
    """Par défaut max_revisions=2."""
    with patch(
        "services.cyber_eval_service.run_pipeline_with_revision",
        return_value=(_tuple("publish"), 0),
    ) as mock_pipeline:
        CyberEvalService().analyze("question")
    mock_pipeline.assert_called_once_with("question", max_revisions=2)
