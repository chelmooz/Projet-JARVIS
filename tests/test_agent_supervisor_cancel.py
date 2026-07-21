"""Tests AgentSupervisor — annulation effective au timeout (audit DevOps 4.1).

Avant : le thread daemon continuait de tourner (requete httpx Ollama non annulee)
apres le timeout. Apres : `cancel_fn` est appele au timeout pour annuler la
requete sous-jacente (fermeture du client HTTP), evitant le thread 'zombie'.
"""
import time
from unittest import mock

from agents.supervisor import AgentSupervisor
from services.inference import InferenceService


def test_supervisor_calls_cancel_on_timeout():
    agent = mock.MagicMock()
    agent.run.side_effect = lambda *a, **k: time.sleep(0.5) or {"response": "done"}
    sv = AgentSupervisor(timeout=0.1)
    calls = []
    res = sv.run(agent, "t", "m", {}, cancel_fn=lambda: calls.append(1))
    assert res["timeout"] is True
    assert calls == [1]


def test_supervisor_no_cancel_when_fast():
    agent = mock.MagicMock()
    agent.run.return_value = {"response": "ok"}
    sv = AgentSupervisor(timeout=1)
    cancel = mock.MagicMock()
    res = sv.run(agent, "t", "m", {}, cancel_fn=cancel)
    assert res["response"] == "ok"
    cancel.assert_not_called()


def test_inference_cancel_current_closes_adapter():
    svc = InferenceService()
    adapter = mock.MagicMock()
    svc._registry = mock.MagicMock()
    svc._registry.get.return_value = adapter
    svc.cancel_current()
    adapter.close.assert_called_once()
