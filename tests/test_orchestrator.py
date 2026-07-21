"""Tests pour OrchestratorService — Coordination métier."""
from unittest.mock import MagicMock, patch

import pytest

from services.orchestrator import OrchestratorService


@pytest.fixture
def mocks():
    return {
        "inference": MagicMock(),
        "memory": MagicMock(),
        "vector": MagicMock(),
        "log": MagicMock(),
        "analytics": MagicMock(),
        "conversations": MagicMock(),
        "metrics": MagicMock(),
        "agents": {"vision": MagicMock()},
        "router_service": MagicMock(),
        "toolbox": MagicMock(),
    }


@pytest.fixture
def graph_factory():
    g = MagicMock()
    g.run.return_value = {
        "response": "ok", "agent": "dev", "model": "phi4-mini",
    }
    return lambda: g


@pytest.fixture
def service(mocks, graph_factory):
    svc = OrchestratorService(
        inference=mocks["inference"], memory=mocks["memory"],
        vector=mocks["vector"], log=mocks["log"],
        analytics=mocks["analytics"], conversations=mocks["conversations"],
        metrics=mocks["metrics"], agents=mocks["agents"],
        router_service=mocks["router_service"], toolbox=mocks["toolbox"],
        agent_graph_factory=graph_factory,
    )
    return svc


class TestHandleRequest:
    def test_returns_dict_without_image(self, service, mocks):
        result = service.handle_request("debug code", None, None)
        assert isinstance(result, dict)
        assert result["response"] == "ok"
        mocks["metrics"].incr_requests.assert_called_once_with("/api/jarvis")

    def test_returns_dict_with_image(self, service, mocks):
        mocks["agents"]["vision"].run.return_value = {
            "response": "vision ok", "agent": "vision", "model": "llava",
        }
        with patch("services.orchestrator.select_vision_model", return_value="llava"):
            result = service.handle_request("describe this image", "base64...", None)
        assert isinstance(result, dict)

    def test_with_conv_id_does_not_save_messages(self, service, mocks):
        # ADR-004 : la persistance (save_conv/track_query) est déplacée dans le
        # routeur HTTP, pas l'orchestrateur. L'orchestrateur ne doit PAS écrire.
        service.handle_request("debug", None, "conv123")
        mocks["conversations"].add_message.assert_not_called()

    def test_calls_graph_with_conv_id(self, service, mocks, graph_factory):
        g = graph_factory()
        service.handle_request("debug", None, "conv42")
        g.run.assert_called_once()
        call_kwargs = g.run.call_args[1]
        assert call_kwargs.get("conversation_id") == "conv42"

    def test_graph_failure_returns_fallback(self, service, mocks, graph_factory):
        g = graph_factory()
        g.run.side_effect = RuntimeError("Ollama down")
        mocks["router_service"].select_agent.return_value = "cyber"
        result = service.handle_request("scan network", None, None)
        assert "response" in result
        assert "simulation" in result["response"].lower()

    def test_graph_failure_logs_error(self, service, mocks, graph_factory):
        g = graph_factory()
        g.run.side_effect = RuntimeError("Ollama down")
        mocks["router_service"].select_agent.return_value = "cyber"
        service.handle_request("scan network", None, None)
        mocks["log"].log.assert_any_call("ERROR", mocks["log"].log.call_args[0][1])


class TestSimulationResponse:
    def test_returns_dict_with_expected_keys(self, service):
        result = service._simulation_response("task", "dev", "error msg", 0.0)
        assert "response" in result
        assert result["agent"] == "dev"
        assert "backend" in result
        assert result["suggested_skill"] is None

    def test_contains_error_in_response(self, service):
        result = service._simulation_response("task", "cyber", "connection refused", 1.0)
        assert "connection refused" in result["response"]


class TestRunVision:
    def test_calls_vision_agent(self, service, mocks):
        mocks["agents"]["vision"].run.return_value = {
            "response": "vision desc", "agent": "vision", "model": "llava",
        }
        result = service._run_vision("describe", "llava", {}, "vision", 0.0)
        mocks["agents"]["vision"].run.assert_called_once_with("describe", "llava", {})
        assert result["response"] == "vision desc"

    def test_updates_habits(self, service, mocks):
        mocks["agents"]["vision"].run.return_value = {
            "response": "ok", "agent": "vision", "model": "llava",
        }
        service._run_vision("task", "llava", {}, "vision", 0.0)
        mocks["memory"].update_habits.assert_called_once()

    def test_exception_returns_error_dict(self, service, mocks):
        mocks["agents"]["vision"].run.side_effect = ValueError("vision model crashed")
        result = service._run_vision("task", "llava", {}, "vision", 0.0)
        assert "error" in result
        assert "vision model crashed" in result["error"]
