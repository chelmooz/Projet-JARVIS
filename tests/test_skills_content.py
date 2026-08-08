"""Tests de contenu de config/skills.json — structure, fusion Superpowers, nouveau skill.

Ces tests chargent le VRAI fichier de configuration via load_skills() et
verifient les regles de contenu issues de l'integration selective de
obra/superpowers (ticket BACKLOG : fusion TDD dans kill_coding, checklist
de revue dans code_review, nouveau skill systematic_debugging).
"""
import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.skills import load_skills

REQUIRED_KEYS = {"id", "name", "description", "category", "enabled", "prompt"}


def _skills() -> list[dict]:
    """Retourne la liste des skills du vrai config/skills.json."""
    data = load_skills()
    return data.get("skills", [])


class TestSkillsFileStructure:
    """Invariants structurels de config/skills.json."""

    def test_no_duplicate_ids(self):
        ids = [s["id"] for s in _skills()]
        assert len(ids) == len(set(ids))

    def test_all_entries_have_required_keys(self):
        for skill in _skills():
            assert REQUIRED_KEYS.issubset(skill.keys())

    def test_new_skills_disabled_by_default(self):
        for skill in _skills():
            assert skill["enabled"] is False


class TestKillCodingSkill:
    """kill_coding : fusion du contenu TDD de obra/superpowers."""

    def _kill_coding_prompt(self) -> str:
        skill = next(s for s in _skills() if s["id"] == "kill_coding")
        return skill["prompt"]

    def test_contains_iron_law(self):
        assert "iron law" in self._kill_coding_prompt().lower()

    def test_contains_test_antipatterns(self):
        prompt = self._kill_coding_prompt().lower()
        assert ("assertion miroir" in prompt) or ("anti-pattern" in prompt)

    def test_contains_change_detector_rule(self):
        assert "change detector" in self._kill_coding_prompt().lower()


class TestCodeReviewSkill:
    """code_review : fusionne la checklist de revue de obra/superpowers."""

    def _code_review_prompt(self) -> str:
        skill = next(s for s in _skills() if s["id"] == "code_review")
        return skill["prompt"]

    def test_contains_plan_alignment(self):
        assert "alignement au plan" in self._code_review_prompt().lower()

    def test_contains_production_readiness(self):
        assert "production readiness" in self._code_review_prompt().lower()


class TestSystematicDebuggingSkill:
    """systematic_debugging : nouveau skill adapte de obra/superpowers."""

    def _skill(self) -> dict:
        for s in _skills():
            if s["id"] == "systematic_debugging":
                return s
        raise AssertionError("skill 'systematic_debugging' absent de config/skills.json")

    def test_skill_exists_with_required_keys(self):
        assert REQUIRED_KEYS.issubset(self._skill().keys())

    def test_disabled_by_default(self):
        assert self._skill()["enabled"] is False

    def test_prompt_contains_four_phases(self):
        prompt = self._skill()["prompt"]
        assert "phase 1" in prompt.lower()
        assert "phase 4" in prompt.lower()

    def test_prompt_contains_three_fixes_rule(self):
        assert "3 correctifs" in self._skill()["prompt"]

    def test_prompt_contains_root_cause_rule(self):
        assert "cause racine" in self._skill()["prompt"]
