"""Tests des contrats Pydantic des agents d'évaluation (MT-Lot12-L2).

Vérifie les contraintes Field()/Literal de ``agents.eval_contracts`` :
bornes de score, valeurs énumérées (hallucination_risk, decision).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agents.eval_contracts import AdvocateOutput, EvaluatorOutput, JudgeOutput


def test_judge_output_valide_ok() -> None:
    output = JudgeOutput(
        score=0.85,
        critique="Réponse correcte et complète.",
        checks_passed=["factualite", "coherence"],
        flags=["omission_source"],
        confidence=0.9,
    )
    assert output.score == 0.85
    assert output.critique == "Réponse correcte et complète."
    assert output.checks_passed == ["factualite", "coherence"]
    assert output.flags == ["omission_source"]
    assert output.confidence == 0.9


def test_judge_output_score_trop_eleve_erreur() -> None:
    with pytest.raises(ValidationError):
        JudgeOutput(score=1.5, critique="x", confidence=0.5)


def test_judge_output_score_negatif_erreur() -> None:
    with pytest.raises(ValidationError):
        JudgeOutput(score=-0.1, critique="x", confidence=0.5)


def test_advocate_output_risque_hallucination_invalide_erreur() -> None:
    with pytest.raises(ValidationError):
        AdvocateOutput(
            score=0.5,
            faille="x",
            hallucination_risk="extreme",
            confidence=0.5,
        )


def test_evaluator_output_decision_publish_valide() -> None:
    output = EvaluatorOutput(
        decision="publish",
        final_score=0.9,
        reasoning="Toutes les vérifications sont passées.",
        revision_instructions=None,
        verified_tier="machine-confirmed",
        confidence=0.95,
    )
    assert output.decision == "publish"
    assert output.final_score == 0.9
    assert output.verified_tier == "machine-confirmed"


def test_evaluator_output_decision_invalide_erreur() -> None:
    with pytest.raises(ValidationError):
        EvaluatorOutput(
            decision="delete",
            final_score=0.5,
            reasoning="x",
            confidence=0.5,
        )
