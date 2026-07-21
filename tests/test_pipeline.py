"""Tests PipelineEngine."""
import os
import sys

import pytest
import yaml

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from models import Pipeline, PipeStep
from services.pipeline import PipelineEngine, PipelineError


class FakeAgentRunner:
    def __call__(self, agent_key, prompt):
        return f"{agent_key}: {prompt[:20]}"


class FakeInference:
    def query(self, prompt, model):
        return f"ok: {prompt[:20]}"


class FakeMemory:
    def update_habits(self, data):
        pass


class TestPipelineEngine:
    def test_register_and_list(self):
        eng = PipelineEngine()
        p = Pipeline(id="test", steps=[PipeStep(name="s1", agent_key="dev", prompt_template="do {task}")])
        eng.register(p)
        lst = eng.list()
        assert any(x["id"] == "test" for x in lst)

    def test_run_single_step(self):
        eng = PipelineEngine(agent_runner=FakeAgentRunner())
        eng.register(Pipeline(id="test", steps=[PipeStep(name="s1", agent_key="dev", prompt_template="do {task}")]))
        result = eng.run("test", "hello")
        assert result["pipeline"] == "test"
        assert result["steps"] == 1
        assert result["error"] is None
        assert "dev:" in result["results"][0]["response"]

    def test_run_multi_step(self):
        eng = PipelineEngine(agent_runner=FakeAgentRunner())
        eng.register(Pipeline(id="multi", steps=[
            PipeStep(name="s1", agent_key="cyber", prompt_template="scan {task}"),
            PipeStep(name="s2", agent_key="dev", prompt_template="fix {task}"),
        ]))
        result = eng.run("multi", "test")
        assert result["steps"] == 2
        assert result["error"] is None

    def test_run_unknown_pipeline(self):
        eng = PipelineEngine()
        with pytest.raises(PipelineError):
            eng.run("nope", "test")

    def test_abort_on_error(self):
        class BrokenRunner:
            def __call__(self, agent_key, prompt):
                raise RuntimeError("broken")
        eng = PipelineEngine(agent_runner=BrokenRunner())
        eng.register(Pipeline(id="test", steps=[
            PipeStep(name="s1", agent_key="dev", prompt_template="do {task}", on_error="abort"),
        ]))
        result = eng.run("test", "hello")
        assert result["error"] is not None

    def test_skip_on_error(self):
        class SkipRunner:
            def __call__(self, agent_key, prompt):
                if agent_key == "cyber":
                    raise RuntimeError("skip me")
                return "ok"
        eng = PipelineEngine(agent_runner=SkipRunner())
        eng.register(Pipeline(id="test", steps=[
            PipeStep(name="s1", agent_key="cyber", prompt_template="scan {task}", on_error="skip"),
            PipeStep(name="s2", agent_key="dev", prompt_template="fix {task}"),
        ]))
        result = eng.run("test", "hello")
        assert result["error"] is None
        assert result["steps"] == 2

    def test_run_with_inference_fallback(self):
        eng = PipelineEngine(inference=FakeInference())
        eng.register(Pipeline(id="test", steps=[PipeStep(name="s1", agent_key="", prompt_template="do {task}")]))
        result = eng.run("test", "hello")
        assert result["steps"] == 1
        assert "ok:" in result["results"][0]["response"]

    def test_load_from_yaml(self, tmpdir):
        pipelines_dir = os.path.join(tmpdir, "pipelines")
        os.makedirs(pipelines_dir)
        with open(os.path.join(pipelines_dir, "test.yaml"), "w") as f:
            yaml.dump({
                "pipeline": {
                    "id": "yaml_test", "on_error": "abort",
                    "steps": [{"name": "s1", "agent_key": "dev", "prompt_template": "do {task}"}],
                }
            }, f)
        import services.pipeline as pmod
        old = pmod.PIPELINES_DIR
        try:
            pmod.PIPELINES_DIR = pipelines_dir
            eng = PipelineEngine(agent_runner=FakeAgentRunner())
            lst = eng.list()
            assert any(x["id"] == "yaml_test" for x in lst)
        finally:
            pmod.PIPELINES_DIR = old
