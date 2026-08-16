"""Tests du chargeur de prompts SKILL d'évaluation (MT-Lot12-L3)."""

from __future__ import annotations

import pytest

from agents.skills_eval import load_skill_eval


def test_load_judge_retourne_texte_non_vide() -> None:
    assert len(load_skill_eval("judge")) > 0


def test_load_advocate_retourne_texte_non_vide() -> None:
    assert len(load_skill_eval("advocate")) > 0


def test_load_evaluator_retourne_texte_non_vide() -> None:
    assert len(load_skill_eval("evaluator")) > 0


def test_load_unknown_leve_value_error() -> None:
    with pytest.raises(ValueError, match="Rôle inconnu"):
        load_skill_eval("unknown")


def test_load_roles_contiennent_les_contrats() -> None:
    assert "judge_output_v1" in load_skill_eval("judge")
    assert "advocate_output_v1" in load_skill_eval("advocate")
    assert "evaluator_output_v1" in load_skill_eval("evaluator")
