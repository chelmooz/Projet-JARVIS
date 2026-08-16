"""Orchestrateur multi-agents : judge → advocate → evaluator."""

from __future__ import annotations

import json
from typing import Any

from agents.eval_contracts import AdvocateOutput, EvaluatorOutput, JudgeOutput
from agents.ollama_client import generate_json
from agents.parsing import parse_model
from agents.skills_eval import load_skill_eval


def _judge_prompt(question: str) -> str:
    return load_skill_eval("judge") + "\n\nQuestion:\n" + question


def _advocate_prompt(question: str, judge_dict: dict[str, Any]) -> str:
    return (
        load_skill_eval("advocate")
        + "\n\nQuestion:\n"
        + question
        + "\n\nJudge output:\n"
        + json.dumps(judge_dict, ensure_ascii=False)
    )


def _evaluator_prompt(question: str, judge_dict: dict[str, Any], advocate_dict: dict[str, Any]) -> str:
    return (
        load_skill_eval("evaluator")
        + "\n\nQuestion:\n"
        + question
        + "\n\nJudge:\n"
        + json.dumps(judge_dict, ensure_ascii=False)
        + "\n\nAdvocate:\n"
        + json.dumps(advocate_dict, ensure_ascii=False)
    )


def run_pipeline(
    question: str,
) -> tuple[JudgeOutput, AdvocateOutput, EvaluatorOutput] | None:
    """Exécute le pipeline judge → advocate → evaluator sur la question.

    Retourne le tuple des 3 sorties validées, ou ``None`` si un agent échoue
    (``generate_json`` → ``None`` ou ``parse_model`` → ``None``).
    """
    judge_dict = generate_json(_judge_prompt(question))
    if judge_dict is None:
        return None
    judge_output = parse_model(JudgeOutput, json.dumps(judge_dict, ensure_ascii=False))
    if judge_output is None:
        return None

    advocate_dict = generate_json(_advocate_prompt(question, judge_dict))
    if advocate_dict is None:
        return None
    advocate_output = parse_model(AdvocateOutput, json.dumps(advocate_dict, ensure_ascii=False))
    if advocate_output is None:
        return None

    evaluator_dict = generate_json(_evaluator_prompt(question, judge_dict, advocate_dict))
    if evaluator_dict is None:
        return None
    evaluator_output = parse_model(EvaluatorOutput, json.dumps(evaluator_dict, ensure_ascii=False))
    if evaluator_output is None:
        return None

    return judge_output, advocate_output, evaluator_output
