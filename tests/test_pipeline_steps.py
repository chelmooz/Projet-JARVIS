"""Tests TDD — Pipeline Steps : query_model propage tool_results (bug T1).

RED → GREEN : `query_model` doit transmettre à l'agent le même dict
`context` enrichi de `tool_results`, même quand `state` ne possède pas de
clé "context" pré-existante (aucune dépendance à un pré-remplissage externe).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from services.pipeline_steps import query_model, select_model


class TestSelectModel:
    """RED → GREEN : select_model(agent_key, ...) ne doit jamais passer
    agent_key directement à resolve_model() — ce n'est pas un nom de
    modèle. Bug réel observé : "techlead"/"dev"/etc. ne matchent jamais
    rien, le fallback first_available() tombe sur le 1er modèle de
    /api/tags, potentiellement un modèle embedding-only -> 400 Bad
    Request sur /api/generate en conditions réelles (clé USB, 07/08/2026).
    """

    def test_explicit_model_wins_over_everything(self):
        provider = MagicMock()
        assert select_model("techlead", "explicit-model", provider) == "explicit-model"
        provider.resolve_model.assert_not_called()

    def test_resolves_via_agent_profile_not_via_agent_key(self, monkeypatch):
        import services.pipeline_steps as pipeline_steps_module
        monkeypatch.setattr(
            pipeline_steps_module, "model_for_agent",
            lambda key: "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M" if key == "techlead" else None,
        )
        provider = MagicMock()
        provider.resolve_model.side_effect = lambda name: name if name == "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M" else None
        provider.first_available.return_value = "hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M"

        result = select_model("techlead", None, provider)

        assert result == "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"
        provider.resolve_model.assert_called_with("hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M")
        provider.first_available.assert_not_called()

    def test_falls_back_to_first_available_when_profile_unresolvable(self, monkeypatch):
        import services.pipeline_steps as pipeline_steps_module
        monkeypatch.setattr(pipeline_steps_module, "model_for_agent", lambda key: None)
        provider = MagicMock()
        provider.resolve_model.return_value = None
        provider.first_available.return_value = "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"

        result = select_model("techlead", None, provider)

        assert result == "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"

    def test_raises_when_nothing_available(self, monkeypatch):
        import services.pipeline_steps as pipeline_steps_module
        monkeypatch.setattr(pipeline_steps_module, "model_for_agent", lambda key: None)
        provider = MagicMock()
        provider.resolve_model.return_value = None
        provider.first_available.return_value = None

        try:
            select_model("techlead", None, provider)
            raise AssertionError("devrait lever RuntimeError")
        except RuntimeError:
            pass


class _RecordingAgent:
    """Agent factice qui capture le context reçu par run()."""

    def __init__(self) -> None:
        self.received_context: dict | None = None

    def run(self, prompt, model, context):
        self.received_context = context
        return {"response": "ok", "agent": "hardware", "model": model}


class _Toolbox:
    """Toolbox factice : déclenche witr pour 'pourquoi ... tourne'."""

    def auto_execute(self, task: str) -> dict:
        if "pourquoi" in task:
            return {"why_running": {"tool": "witr", "success": True, "data": {"PID": 1}}}
        return {}


class _Provider:
    def resolve_model(self, agent_key):
        return "model-x"

    def first_available(self):
        return "model-x"


def _model_selector(agent_key: str, model: str | None, provider: Any) -> str:
    return model or "model-x"


class TestQueryModelToolResults:

    def test_tool_results_reach_agent_without_pre_existing_context(self):
        agent = _RecordingAgent()
        state = {"agent_key": "hardware", "task": "pourquoi explorer tourne"}
        query_model(state, _Provider(), {"hardware": agent}, _Toolbox(), _model_selector)
        tool_results = agent.received_context["tool_results"]
        assert tool_results["why_running"]["tool"] == "witr"

    def test_tool_results_reach_agent_with_existing_context(self):
        agent = _RecordingAgent()
        state = {"agent_key": "hardware", "task": "pourquoi explorer tourne",
                 "context": {"habits": ["x"]}}
        query_model(state, _Provider(), {"hardware": agent}, _Toolbox(), _model_selector)
        tool_results = agent.received_context["tool_results"]
        assert tool_results["why_running"]["tool"] == "witr"
        assert agent.received_context["habits"] == ["x"]

    def test_context_is_persisted_in_state_for_later_steps(self):
        agent = _RecordingAgent()
        state = {"agent_key": "hardware", "task": "pourquoi explorer tourne"}
        query_model(state, _Provider(), {"hardware": agent}, _Toolbox(), _model_selector)
        assert "tool_results" in state["context"]

    def test_agent_missing_returns_friendly_error(self):
        state = {"agent_key": "ghost", "task": "pourquoi explorer tourne"}
        result = query_model(state, _Provider(), {}, _Toolbox(), _model_selector)
        assert result["error"] is not None
        assert result["response"]

    def test_empty_task_short_circuits(self):
        state = {"agent_key": "hardware", "task": ""}
        result = query_model(state, _Provider(), {"hardware": _RecordingAgent()},
                             _Toolbox(), _model_selector)
        assert result["error"] == "Tâche vide — rien à exécuter"


class TestQueryModelCompatibility:

    def test_delegates_to_run_and_copies_response(self):
        agent = MagicMock()
        agent.run.return_value = {"response": "reponse test", "agent": "dev", "model": "m"}
        state = {"agent_key": "dev", "task": "ecris un script"}
        result = query_model(state, _Provider(), {"dev": agent}, None, _model_selector)
        assert result["response"] == "reponse test"
        assert result["suggested_skill"] is None

    def test_toolbox_exception_is_swallowed(self):
        agent = _RecordingAgent()

        class BrokenToolbox:
            def auto_execute(self, task):
                raise RuntimeError("toolbox down")

        state = {"agent_key": "hardware", "task": "pourquoi explorer tourne"}
        result = query_model(state, _Provider(), {"hardware": agent},
                             BrokenToolbox(), _model_selector)
        assert result.get("error") is None
        assert agent.received_context["tool_results"] == {}
