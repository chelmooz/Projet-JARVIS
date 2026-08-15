from __future__ import annotations

from types import SimpleNamespace

import services.pipeline as pipeline_module
from models import Pipeline, PipeStep
from services.pipeline import PipelineError, PipelineService


def one_step(on_error: str = "abort") -> Pipeline:
    return Pipeline(
        id="p",
        steps=(PipeStep(name="step", agent_key="dev", prompt_template="{task}", on_error=on_error),),
        on_error=on_error,
    )


def test_load_pipelines_ignores_missing_dir_and_non_yaml(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pipeline_module, "PIPELINES_DIR", str(tmp_path / "missing"))
    service = PipelineService()
    assert service.list_pipelines() == []
    directory = tmp_path / "pipelines"
    directory.mkdir()
    (directory / "notes.txt").write_text("ignored", encoding="utf-8")
    monkeypatch.setattr(pipeline_module, "PIPELINES_DIR", str(directory))
    service._load_pipelines()
    assert service.list_pipelines() == []


def test_load_single_pipeline_valid_duplicate_invalid(monkeypatch, tmp_path) -> None:
    directory = tmp_path / "pipelines"
    directory.mkdir()
    (directory / "a.yaml").write_text("pipeline:\n  id: p\n  steps: []\n", encoding="utf-8")
    (directory / "b.yaml").write_text("pipeline:\n  id: p\n  steps: []\n", encoding="utf-8")
    (directory / "bad.yaml").write_text("invalid: [", encoding="utf-8")
    monkeypatch.setattr(pipeline_module, "PIPELINES_DIR", str(directory))
    service = PipelineService()
    assert service.get("p") is not None
    assert service.list_pipelines() == [{"id": "p", "steps": 0, "on_error": "abort"}]


def test_register_get_resolve_and_run_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pipeline_module, "PIPELINES_DIR", str(tmp_path / "missing"))
    service = PipelineService()
    service.register(one_step())
    assert service.get("p") is not None
    assert service.get("p").steps[0].name == "step"
    try:
        service.run("missing", "task")
    except PipelineError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("PipelineError attendu")


def test_run_inference_response_shapes() -> None:
    class Inference:
        def __init__(self, value):
            self.value = value

        def query(self, prompt, model):
            return self.value

    for value, expected in [
        (SimpleNamespace(data={"response": "data"}), "data"),
        ({"response": "dict"}, "dict"),
        ("raw", "raw"),
    ]:
        service = PipelineService(inference=Inference(value))
        service.register(one_step())
        result = service.run("p", "task")
        assert result["error"] is None
        assert result["results"][0]["response"] == expected


def test_retrieve_similar_cases_success_and_failure() -> None:
    class Vector:
        def search(self, task, top_k):
            if task == "bad":
                raise RuntimeError("vector")
            return [{"id": "1", "text": "case"}]

    service = PipelineService(vector_search=Vector())
    assert service._retrieve_similar_cases("ok") == [{"id": "1", "text": "case"}]
    assert service._retrieve_similar_cases("bad") == []
    assert PipelineService()._retrieve_similar_cases("none") == []


def test_run_legacy_failure_success_and_context() -> None:
    service = PipelineService(inference=None)
    service.register(one_step())
    failure = service.run("p", "task")
    assert failure["error"] is not None

    class Inference:
        def query(self, prompt, model):
            return {"response": "ok"}

    service = PipelineService(inference=Inference())
    service.register(one_step())
    result = service.run("p", "task", {"extra": "x"})
    assert result["error"] is None
    assert result["steps"] == 1


def test_write_checkpoint_and_capitalize_trace() -> None:
    class Store:
        def __init__(self):
            self.records = []

        def append(self, record):
            self.records.append(record)

    store = Store()
    service = PipelineService(trace_store=store)
    service._write_checkpoint("p", "q", 1)
    service._capitalize_trace("p", "q", [{"id": "c", "text": "t"}], "response")
    assert [r.status if hasattr(r, "status") else r.judge_reason for r in store.records] == ["checkpoint", ""]


def test_build_trace_record_uses_judge_when_score_missing() -> None:
    class Judge:
        def evaluate(self, task, chunks, response):
            return {"score": 0.8, "reason": "good"}

    record = PipelineService(judge=Judge())._build_trace_record("p", "q", [{"id": "x", "text": "t"}], "r")
    assert record.retrieved_chunk_ids == ["x"]
    assert record.judge_score == 0.8
    assert record.judge_reason == "good"


def test_record_habits_optional() -> None:
    class Memory:
        def __init__(self):
            self.entries = []

        def update_habits(self, entry):
            self.entries.append(entry)

    memory = Memory()
    PipelineService(memory=memory)._record_habits(
        "task", "p", PipeStep(name="s", agent_key="dev", prompt_template="{task}")
    )
    assert memory.entries == [{"task": "task", "pipeline": "p", "step": "s"}]
    PipelineService()._record_habits("task", "p", PipeStep(name="s", agent_key="dev", prompt_template="{task}"))


def test_adaptive_judge_accepts_and_retries(monkeypatch) -> None:
    class Judge:
        def __init__(self):
            self.calls = 0

        def evaluate(self, query, chunks, response):
            self.calls += 1
            return {"score": 0.9 if self.calls == 1 else 0.1, "reason": "ok"}

    judge = Judge()
    service = PipelineService(inference=SimpleNamespace(query=lambda prompt, model: {"response": "r"}), judge=judge)
    service.register(one_step())
    result = service.run("p", "task")
    assert result["error"] is None
    assert judge.calls == 1


def test_execute_single_step_runner_instance_and_typeerror_fallback() -> None:
    class Runner:
        def __call__(self, *args):
            if len(args) == 0:
                return self
            return "ok"

        def run(self, *args):
            return "instance"

    service = PipelineService(agent_runner=Runner())
    state = service._execute_single_step({}, PipeStep(name="s", agent_key="dev", prompt_template="{task}"), "task")
    assert state["results"][0]["response"] == "ok"


def test_execute_single_step_retries_error_then_records(monkeypatch) -> None:
    calls = {"n": 0}

    class Inference:
        def query(self, prompt, model):
            calls["n"] += 1
            raise RuntimeError("boom")

    monkeypatch.setattr(pipeline_module, "_wait_before_retry", lambda *args: None)
    service = PipelineService(inference=Inference(), max_retries=1)
    state = service._execute_single_step(
        {},
        PipeStep(name="s", agent_key="dev", prompt_template="{task}", on_error="retry"),
        "task",
    )
    assert calls["n"] == 2
    assert "boom" in state["error"]


def test_execute_all_steps_skips_after_error_and_records_success_habits() -> None:
    class Inference:
        def query(self, prompt, model):
            return {"response": "ok"}

    service = PipelineService(inference=Inference())
    pipeline = Pipeline(
        id="p", steps=(one_step().steps[0], PipeStep(name="s2", agent_key="dev", prompt_template="{task}"))
    )
    results = service._execute_all_steps(pipeline, "task", {})
    assert len(results) == 2


def test_alias_is_pipeline_service() -> None:
    assert pipeline_module.PipelineEngine is PipelineService


def test_load_single_pipeline_without_pipeline_key_is_ignored(tmp_path, monkeypatch) -> None:
    directory = tmp_path / "pipelines"
    directory.mkdir()
    (directory / "empty.yaml").write_text("other: value\n", encoding="utf-8")
    monkeypatch.setattr(pipeline_module, "PIPELINES_DIR", str(directory))
    assert PipelineService().list_pipelines() == []


def test_legacy_run_retrieves_similar_cases(monkeypatch) -> None:
    class Inference:
        def query(self, prompt, model):
            return {"response": "ok"}

    service = PipelineService(inference=Inference())
    service.register(one_step())
    monkeypatch.setattr(service, "_retrieve_similar_cases", lambda task: [{"id": "x", "text": "similar"}])
    assert service.run("p", "task")["error"] is None


def test_adaptive_run_returns_failure_on_fatal_step() -> None:
    class Judge:
        def evaluate(self, *args):
            return {"score": 1.0, "reason": "good"}

    service = PipelineService(judge=Judge())
    service.register(one_step())
    result = service.run("p", "task")
    assert result["error"] is not None


def test_adaptive_run_exhausts_attempts(monkeypatch) -> None:
    class Judge:
        def evaluate(self, *args):
            return {"score": 0.0, "reason": "different"}

    monkeypatch.setattr(pipeline_module, "MAX_ADAPTIVE_ATTEMPTS", 2)
    monkeypatch.setattr(pipeline_module, "is_stagnant", lambda *args: False)
    service = PipelineService(
        inference=SimpleNamespace(query=lambda prompt, model: {"response": "r"}),
        judge=Judge(),
    )
    service.register(one_step())
    result = service.run("p", "task")
    assert result["error"] is None


def test_execute_all_steps_breaks_after_fatal_error() -> None:
    service = PipelineService()
    pipeline = Pipeline(
        id="p",
        steps=(
            PipeStep(name="first", agent_key="dev", prompt_template="{task}"),
            PipeStep(name="second", agent_key="dev", prompt_template="{task}"),
        ),
    )
    assert len(service._execute_all_steps(pipeline, "task", {})) == 1


def test_runner_without_run_method_uses_direct_callable() -> None:
    class Runner:
        def __call__(self, *args):
            if not args:
                return object()
            return "direct"

    service = PipelineService(agent_runner=Runner())
    state = service._execute_single_step({}, one_step().steps[0], "task")
    assert state["results"][0]["response"] == "direct"


def test_missing_backend_retries_and_stops(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_module, "_wait_before_retry", lambda *args: None)
    service = PipelineService(max_retries=1)
    step = PipeStep(name="s", agent_key="dev", prompt_template="{task}", on_error="retry")
    state = service._execute_single_step({}, step, "task")
    assert state["results"][-1]["error"] == "Aucun agent_runner ni inference configuré"


def test_retry_loop_else_sets_fallback_error(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_module, "_should_retry", lambda *args: True)
    monkeypatch.setattr(pipeline_module, "_wait_before_retry", lambda *args: None)
    service = PipelineService(max_retries=1)
    step = PipeStep(name="s", agent_key="dev", prompt_template="{task}", on_error="retry")
    state = service._execute_single_step({}, step, "task")
    assert state["results"][-1]["error"] == "Aucun agent_runner ni inference configuré"


def test_capitalize_trace_logs_store_failure() -> None:
    class Store:
        def append(self, record):
            raise RuntimeError("store")

    PipelineService(trace_store=Store())._capitalize_trace("p", "q", [], "response")
