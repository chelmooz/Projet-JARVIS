"""Tests erreurs AgentGraph — Fallbacks et resilience."""
import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from graph.agent_graph import AgentGraph


class FakeInference:
    def is_available(self, model): return True
    def query(self, prompt, model, **kw): return {"response": "ok", "model": model}
    def first_available(self): return "phi4-mini:3.8b"
    def get_active_backend(self): return "ollama"
    def list_models(self): return ["phi4-mini:3.8b"]


class FakeMemory:
    def get_habits(self): return []
    def update_habits(self, data): pass
    def is_healthy(self): return True


class FakeVector:
    def search(self, q, top_k=5): return []
    def index(self, text, metadata=None): pass
    def is_healthy(self): return True


class FakeConversation:
    def add_message(self, *a, **kw): pass


class FakeToolbox:
    def is_enabled(self): return False
    def auto_execute(self, task): return {}


class TestGraphErrors:
    def test_inference_down_returns_fallback(self):
        class BrokenInference:
            def is_available(self, m): return False
            def first_available(self): return None
            def get_active_backend(self): return "ollama"
        g = AgentGraph(model_provider=BrokenInference(), memory=FakeMemory(), vector_store=FakeVector())
        result = g.run("test")
        assert "response" in result
        assert result.get("agent") != ""

    def test_vector_store_timeout_returns_result(self):
        class TimeoutVector:
            def search(self, q, top_k=5): raise TimeoutError("vector timeout")
            def index(self, text, metadata=None): pass
            def is_healthy(self): return False
        g = AgentGraph(model_provider=FakeInference(), memory=FakeMemory(), vector_store=TimeoutVector())
        result = g.run("test")
        assert "response" in result

    def test_unknown_agent_falls_back_to_generic(self):
        from agents.factory import create_agents
        inference = FakeInference()
        memory = FakeMemory()
        agents = create_agents(inference, memory)
        g = AgentGraph(model_provider=inference, memory=memory,
                       vector_store=FakeVector(), agents=agents)
        result = g.run("some weird task")
        assert "response" in result
        assert result.get("agent") != ""
