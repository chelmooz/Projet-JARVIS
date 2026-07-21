"""Tests TDD pour AgentRouter — RED → GREEN."""
import pytest

from models import Task
from services.router import AgentRouter


class TestAgentRouter:
    router = AgentRouter()

    # ── Priority 1 : Préfixe explicite @agent ──────────────────────────────

    @pytest.mark.parametrize("task,expected", [
        ("@cyber scan", "cyber"),
        ("@dev debug", "dev"),
        ("@network ping", "network"),
        ("@hardware temp", "hardware"),
        ("@vision image", "vision"),
    ])
    def test_prefix_direct(self, task, expected):
        assert self.router.select_agent(task) == expected

    @pytest.mark.parametrize("task,expected", [
        ("@orchestrateur plan", "dev"),
        ("@techlead review", "dev"),
        ("@devops deploy", "dev"),
        ("@designer mockup", "dev"),
        ("@datasecu audit", "cyber"),
    ])
    def test_prefix_alias(self, task, expected):
        assert self.router.select_agent(task) == expected

    # ── Priority 2 : Score de mots-clés ────────────────────────────────────

    @pytest.mark.parametrize("task,expected", [
        ("firewall intrusion", "cyber"),
        ("python script debug", "dev"),
        ("routeur ping ip", "network"),
        ("cpu temperature panne", "hardware"),
        ("screenshot image", "vision"),
    ])
    def test_keyword_scoring(self, task, expected):
        assert self.router.select_agent(task) == expected

    # ── Priority 3 : Fallback ───────────────────────────────────────────────

    @pytest.mark.parametrize("task,expected", [
        ("bonjour", "dev"),
        ("", "dev"),
    ])
    def test_fallback(self, task, expected):
        assert self.router.select_agent(task) == expected

    # ── Edge cases ──────────────────────────────────────────────────────────

    @pytest.mark.parametrize("task,expected", [
        ("PORT", "network"),
    ])
    def test_case_insensitive_keyword(self, task, expected):
        assert self.router.select_agent(task) == expected

    def test_task_object(self):
        result = self.router.select_agent(Task(text="firewall intrusion"))
        assert result == "cyber"

    @pytest.mark.parametrize("task,expected", [
        ("securite python", "cyber"),
    ])
    def test_mixed_keywords_tie_first_wins(self, task, expected):
        assert self.router.select_agent(task) == expected
