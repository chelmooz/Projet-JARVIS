"""Tests de l'orchestrateur multi-agents (``agents/orchestrator.py``).

``generate_json`` et ``load_skill_eval`` sont mockés — zéro appel Ollama réel.
"""

import json
from unittest.mock import patch

from agents.eval_contracts import AdvocateOutput, EvaluatorOutput, JudgeOutput
from agents.orchestrator import run_pipeline

JUDGE_DICT = {"score": 0.9, "critique": "Réponse correcte", "confidence": 0.8}
ADVOCATE_DICT = {"score": 0.6, "faille": "Manque une source", "confidence": 0.7}
EVALUATOR_DICT = {"decision": "revise", "final_score": 0.7, "reasoning": "À réviser", "confidence": 0.6}

PROMPTS = {"judge": "prompt_judge", "advocate": "prompt_advocate", "evaluator": "prompt_evaluator"}


def test_pipeline_returns_all_three_outputs():
    """Trois dicts valides → tuple de 3 instances Pydantic."""
    with (
        patch("agents.orchestrator.load_skill_eval", side_effect=lambda role: PROMPTS[role]),
        patch(
            "agents.orchestrator.generate_json",
            side_effect=[JUDGE_DICT, ADVOCATE_DICT, EVALUATOR_DICT],
        ),
    ):
        result = run_pipeline("question")
    assert result is not None
    judge, advocate, evaluator = result
    assert isinstance(judge, JudgeOutput)
    assert isinstance(advocate, AdvocateOutput)
    assert isinstance(evaluator, EvaluatorOutput)
    assert judge.score == 0.9
    assert advocate.faille == "Manque une source"
    assert evaluator.decision == "revise"


def test_pipeline_returns_none_if_judge_fails():
    """Échec du judge (generate_json → None) → None."""
    with (
        patch("agents.orchestrator.load_skill_eval", side_effect=lambda role: PROMPTS[role]),
        patch("agents.orchestrator.generate_json", side_effect=[None]),
    ):
        assert run_pipeline("question") is None


def test_pipeline_returns_none_if_advocate_fails():
    """Échec de l'avocat → None."""
    with (
        patch("agents.orchestrator.load_skill_eval", side_effect=lambda role: PROMPTS[role]),
        patch("agents.orchestrator.generate_json", side_effect=[JUDGE_DICT, None]),
    ):
        assert run_pipeline("question") is None


def test_pipeline_returns_none_if_evaluator_fails():
    """Échec de l'évaluateur → None."""
    with (
        patch("agents.orchestrator.load_skill_eval", side_effect=lambda role: PROMPTS[role]),
        patch(
            "agents.orchestrator.generate_json",
            side_effect=[JUDGE_DICT, ADVOCATE_DICT, None],
        ),
    ):
        assert run_pipeline("question") is None


def test_pipeline_passes_correct_prompts():
    """Les prompts transmis respectent le format de concaténation validé."""
    received: list[str] = []
    counter = {"n": 0}
    results = [JUDGE_DICT, ADVOCATE_DICT, EVALUATOR_DICT]

    def fake_generate_json(prompt: str, system: str | None = None) -> dict | None:
        received.append(prompt)
        value = results[counter["n"]]
        counter["n"] += 1
        return value

    with (
        patch("agents.orchestrator.load_skill_eval", side_effect=lambda role: PROMPTS[role]),
        patch("agents.orchestrator.generate_json", side_effect=fake_generate_json),
    ):
        run_pipeline("question")

    assert received[0] == "prompt_judge\n\nQuestion:\nquestion"
    assert received[1] == "prompt_advocate\n\nQuestion:\nquestion\n\nJudge output:\n" + json.dumps(
        JUDGE_DICT, ensure_ascii=False
    )
    assert received[2] == "prompt_evaluator\n\nQuestion:\nquestion\n\nJudge:\n" + json.dumps(
        JUDGE_DICT, ensure_ascii=False
    ) + "\n\nAdvocate:\n" + json.dumps(ADVOCATE_DICT, ensure_ascii=False)
