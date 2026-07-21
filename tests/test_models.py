"""Tests RED → GREEN pour les models."""
from models import AgentInput, AgentOutput, Result, Task


def test_result_ok():
    r = Result.ok(data={"content": "hello"}, agent="test", model="phi4")
    assert r.success
    assert r.data["content"] == "hello"
    assert r.agent == "test"


def test_result_fail():
    r = Result.fail(error="oups")
    assert not r.success
    assert r.error == "oups"


def test_task_defaults():
    t = Task(text="hello")
    assert t.text == "hello"
    assert t.image is None
    assert t.conversation_id is None


def test_agent_input_defaults():
    inp = AgentInput(task="hello")
    assert inp.task == "hello"
    assert inp.image is None
    assert inp.model is None


def test_agent_output():
    out = AgentOutput(response="ok", agent="dev", model="phi4")
    assert out.response == "ok"
    assert out.suggested_skill is None
