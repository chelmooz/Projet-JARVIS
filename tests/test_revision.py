"""Tests de la boucle de révision (``agents/revision.py``).

``run_pipeline`` est mocké — zéro appel Ollama réel.
"""

from unittest.mock import patch

from agents.eval_contracts import AdvocateOutput, EvaluatorOutput, JudgeOutput
from agents.revision import run_pipeline_with_revision


def _result(decision: str, revision_instructions: str | None = None):
    judge = JudgeOutput(score=0.9, critique="Réponse correcte", confidence=0.8)
    advocate = AdvocateOutput(score=0.7, faille="Manque une source", confidence=0.7)
    evaluator = EvaluatorOutput(
        decision=decision,
        final_score=0.8,
        reasoning="À réviser",
        revision_instructions=revision_instructions,
        confidence=0.6,
    )
    return judge, advocate, evaluator


def test_no_revision_if_decision_not_revise():
    """Decision ≠ 'revise' → résultat retourné, un seul appel pipeline."""
    with patch("agents.revision.run_pipeline", return_value=_result("publish")) as mock_pipeline:
        result = run_pipeline_with_revision("question")
    assert result is not None
    assert result[2].decision == "publish"
    assert mock_pipeline.call_count == 1


def test_revision_triggered_on_revise_decision():
    """'revise' puis 'accept' → deuxième tuple retourné, 2 appels."""
    with patch(
        "agents.revision.run_pipeline",
        side_effect=[
            _result("revise", "Ajouter source"),
            _result("publish"),
        ],
    ) as mock_pipeline:
        result = run_pipeline_with_revision("question")
    assert result is not None
    assert result[2].decision == "publish"
    assert mock_pipeline.call_count == 2


def test_max_revisions_respected():
    """Toujours 'revise' avec max_revisions=1 → 2 appels (initial + 1 révision)."""
    with patch("agents.revision.run_pipeline", return_value=_result("revise")) as mock_pipeline:
        result = run_pipeline_with_revision("question", max_revisions=1)
    assert result is not None
    assert mock_pipeline.call_count == 2


def test_returns_none_if_all_revisions_fail():
    """Échec du pipeline (None) → None."""
    with patch("agents.revision.run_pipeline", return_value=None) as mock_pipeline:
        assert run_pipeline_with_revision("question") is None
    assert mock_pipeline.call_count == 1


def test_revision_instructions_appended_to_question():
    """La question enrichie inclut les instructions de révision."""
    received: list[str] = []

    def fake_pipeline(question: str):
        received.append(question)
        return _result("revise", "Ajouter source") if len(received) == 1 else _result("publish")

    with patch("agents.revision.run_pipeline", side_effect=fake_pipeline):
        run_pipeline_with_revision("question")

    assert received[0] == "question"
    assert received[1] == "question\n\n[Instructions de révision]:\nAjouter source"
