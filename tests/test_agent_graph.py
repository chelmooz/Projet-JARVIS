"""Tests AgentGraph — Orchestrateur 5 etapes."""
import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from graph.agent_graph import AgentGraph
from services.pipeline import PipelineService
from services.pipeline_steps import format_output, select_agent


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


class TestAgentGraph:
    def test_run_returns_required_keys(self):
        g = AgentGraph(model_provider=FakeInference(), memory=FakeMemory(), vector_store=FakeVector())
        result = g.run("test task")
        assert "response" in result
        assert "agent" in result
        assert "model" in result
        assert "backend" in result

    def test_run_with_image_sets_vision_agent(self):
        g = AgentGraph(model_provider=FakeInference(), memory=FakeMemory(), vector_store=FakeVector())
        result = g.run("describe", image="data:base64,...")
        assert result.get("agent") == "vision"

    def test_run_error_returns_fallback(self):
        class BrokenInference:
            def is_available(self, m): return False
            def first_available(self): return None
            def get_active_backend(self): return "ollama"
        g = AgentGraph(model_provider=BrokenInference(), memory=FakeMemory(), vector_store=FakeVector())
        result = g.run("test")
        assert "response" in result
        assert result.get("agent") != ""

    def test_select_agent_returns_string(self):
        g = AgentGraph(model_provider=FakeInference(), memory=FakeMemory(), vector_store=FakeVector())
        s = select_agent({"task": "analyse ce reseau", "image": None}, g.router)
        assert isinstance(s["agent_key"], str)
        assert len(s["agent_key"]) > 0

    def test_format_output_includes_all_fields(self):
        s = {"response": "hello", "agent_key": "dev", "model": "phi4-mini:3.8b",
             "suggested_skill": None, "result": None}
        out = format_output(s)
        assert out["response"] == "hello"
        assert out["agent"] == "dev"
        assert out["backend"] == "ollama"  # defaut dans format_output

    def test_pipeline_name_fix(self):
        """PipelineService alias doit fonctionner comme PipelineEngine."""
        eng = PipelineService(agent_runner=lambda k, p: "ok")
        assert eng is not None
        assert hasattr(eng, "register")
        assert hasattr(eng, "run")

    def test_graph_with_conversation(self):
        """AgentGraph doit accepter un service de conversation."""
        conv = FakeConversation()
        g = AgentGraph(model_provider=FakeInference(), memory=FakeMemory(),
                       vector_store=FakeVector(), conversations=conv)
        result = g.run("test task", conversation_id="test-conv")
        assert "response" in result

    def test_graph_vector_context(self):
        """AgentGraph doit utiliser le vector store pour le contexte."""
        vs = FakeVector()
        g = AgentGraph(model_provider=FakeInference(), memory=FakeMemory(), vector_store=vs)
        result = g.run("test task")
        assert "response" in result

    def test_graph_skill_suggested(self):
        """Le resultat doit contenir suggested_skill."""
        g = AgentGraph(model_provider=FakeInference(), memory=FakeMemory(), vector_store=FakeVector())
        result = g.run("test task")
        assert "suggested_skill" in result
