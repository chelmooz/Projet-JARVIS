"""TDD — AgentSupervisor (M23c)."""
import time

from agents.supervisor import AgentSupervisor


class _SlowAgent:
    _profile_key = "dev"

    def run(self, task, model, context):
        time.sleep(2)
        return {"response": "ok", "agent": "dev", "model": model}


class _FastAgent:
    _profile_key = "dev"

    def run(self, task, model, context):
        return {"response": "fast", "agent": "dev", "model": model}


class _BoomAgent:
    _profile_key = "dev"

    def run(self, task, model, context):
        raise RuntimeError("kaboom")


def test_supervisor_returns_result_when_fast():
    s = AgentSupervisor(timeout=1)
    out = s.run(_FastAgent(), "t", "m", {})
    assert out["response"] == "fast"


def test_supervisor_timeout_returns_structured_error():
    s = AgentSupervisor(timeout=1)
    out = s.run(_SlowAgent(), "t", "m", {})
    assert out.get("timeout") is True
    assert "Timeout" in out["response"]


def test_supervisor_propagates_exception():
    s = AgentSupervisor(timeout=1)
    try:
        s.run(_BoomAgent(), "t", "m", {})
        assert False, "devait lever"
    except RuntimeError as e:
        assert "kaboom" in str(e)
