#!/usr/bin/env python3
"""Caractérisation de services/pipeline_steps.py (Lot 1).

Couvre les 6 étapes unitaires de l'orchestration séquentielle :
select_agent, select_model, retrieve_context, query_model,
save_results, format_output — plus les helpers privés de retry
(_should_retry, _wait_before_retry, _runner_supports_model).
"""

from __future__ import annotations

from typing import Any

import pytest

from services.pipeline_steps import (
    MAX_ERROR_LENGTH,
    RETRY_DELAY,
    NonCallableRunnerError,
    _runner_supports_model,
    _should_retry,
    _wait_before_retry,
    format_output,
    query_model,
    retrieve_context,
    save_results,
    select_agent,
    select_model,
)

# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class FakeStep:
    def __init__(self, on_error: str = "retry") -> None:
        self.on_error = on_error


class FakeRouter:
    def __init__(self, agent_key: str = "network") -> None:
        self.agent_key = agent_key
        self.last_task: str | None = None

    def select_agent(self, task: str) -> str:
        self.last_task = task
        return self.agent_key


class FakeProvider:
    def __init__(
        self,
        resolve_result: str | None = "resolved-model",
        first_available_result: str | None = "fallback-model",
        has_resolve: bool = True,
        has_first_available: bool = True,
    ) -> None:
        self._resolve_result = resolve_result
        self._first_available_result = first_available_result
        self._has_resolve = has_resolve
        self._has_first_available = has_first_available
        self.resolve_calls: list[str | None] = []
        self.first_available_calls = 0
        if has_resolve:
            self.resolve_model = self._resolve_model  # type: ignore[attr-defined]
        if has_first_available:
            self.first_available = self._first_available  # type: ignore[attr-defined]

    def _resolve_model(self, configured: str | None) -> str | None:
        self.resolve_calls.append(configured)
        return self._resolve_result

    def _first_available(self) -> str | None:
        self.first_available_calls += 1
        return self._first_available_result


class FakeMemory:
    def __init__(self, habits: list[str] | None = None, raises: bool = False) -> None:
        self._habits = habits
        self._raises = raises

    def get_habits(self, limit: int = 5) -> list[str] | None:
        if self._raises:
            raise RuntimeError("mémoire indisponible")
        return self._habits


class FakeVectorStore:
    def __init__(
        self,
        search_results: list[Any] | None = None,
        raises_on_search: bool = False,
        raises_on_index: bool = False,
    ) -> None:
        self._search_results = search_results
        self._raises_on_search = raises_on_search
        self._raises_on_index = raises_on_index
        self.indexed: list[tuple[str, dict[str, Any]]] = []

    def search(self, task: str, top_k: int = 3) -> list[Any] | None:
        if self._raises_on_search:
            raise RuntimeError("vector store indisponible")
        return self._search_results

    def index(self, response: str, metadata: dict[str, Any]) -> None:
        if self._raises_on_index:
            raise RuntimeError("indexation échouée")
        self.indexed.append((response, metadata))


class FakeAgentWithRun:
    def __init__(self, result: Any = "ok", raises: bool = False) -> None:
        self._result = result
        self._raises = raises
        self.last_call: dict[str, Any] | None = None

    def run(self, prompt: str, model: str | None = None, context: dict[str, Any] | None = None) -> Any:
        self.last_call = {"prompt": prompt, "model": model, "context": context}
        if self._raises:
            raise RuntimeError("agent en erreur")
        return self._result


class FakeAgentWithQuery:
    def __init__(self, result: Any = "queried") -> None:
        self._result = result
        self.last_call: dict[str, Any] | None = None

    def query(self, prompt: str, model: str | None = None) -> Any:
        self.last_call = {"prompt": prompt, "model": model}
        return self._result


class FakeAgentBare:
    """Ni run() ni query() : le fallback str(agent) doit s'appliquer."""

    def __str__(self) -> str:
        return "agent-bare"


class FakeToolbox:
    def __init__(self, result: dict[str, Any] | None = None, raises: bool = False) -> None:
        self._result = result
        self._raises = raises
        self.called_with: str | None = None

    def auto_execute(self, task: str) -> dict[str, Any] | None:
        self.called_with = task
        if self._raises:
            raise RuntimeError("toolbox indisponible")
        return self._result


# ---------------------------------------------------------------------------
# select_agent
# ---------------------------------------------------------------------------


def test_select_agent_with_image_forces_vision() -> None:
    state = {"image": "base64...", "task": "decrire"}
    router = FakeRouter(agent_key="dev")
    result = select_agent(state, router)
    assert result["agent_key"] == "vision"
    assert router.last_task is None  # le router n'est même pas consulté


def test_select_agent_uses_router_when_no_image() -> None:
    state = {"task": "configure le pare-feu"}
    router = FakeRouter(agent_key="network")
    result = select_agent(state, router)
    assert result["agent_key"] == "network"
    assert router.last_task == "configure le pare-feu"


def test_select_agent_defaults_to_dev_without_router() -> None:
    state = {"task": "quelque chose"}
    result = select_agent(state, router=None)
    assert result["agent_key"] == "dev"


# ---------------------------------------------------------------------------
# select_model
# ---------------------------------------------------------------------------


def test_select_model_returns_explicit_model_untouched() -> None:
    provider = FakeProvider()
    model = select_model("dev", "llama3.2", provider)
    assert model == "llama3.2"
    assert provider.resolve_calls == []  # court-circuit, provider jamais consulté


def test_select_model_uses_resolve_model_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.pipeline_steps.model_for_agent", lambda agent_key: "qwen2.5")
    provider = FakeProvider(resolve_result="qwen2.5-final")
    model = select_model("techlead", None, provider)
    assert model == "qwen2.5-final"
    assert provider.resolve_calls == ["qwen2.5"]


def test_select_model_falls_back_to_first_available_when_unresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.pipeline_steps.model_for_agent", lambda agent_key: None)
    provider = FakeProvider(resolve_result=None, first_available_result="mistral")
    model = select_model("dev", None, provider)
    assert model == "mistral"
    assert provider.first_available_calls == 1


def test_select_model_falls_back_when_resolve_model_missing() -> None:
    provider = FakeProvider(has_resolve=False, first_available_result="phi3")
    model = select_model("dev", None, provider)
    assert model == "phi3"


def test_select_model_raises_when_nothing_available() -> None:
    provider = FakeProvider(has_resolve=False, has_first_available=False)
    with pytest.raises(RuntimeError, match="Aucun modèle disponible"):
        select_model("dev", None, provider)


def test_select_model_raises_when_first_available_returns_empty() -> None:
    provider = FakeProvider(has_resolve=False, first_available_result=None)
    with pytest.raises(RuntimeError):
        select_model("dev", None, provider)


# ---------------------------------------------------------------------------
# retrieve_context
# ---------------------------------------------------------------------------


def test_retrieve_context_with_habits_and_similar_cases() -> None:
    state = {"task": "deploie l'app"}
    memory = FakeMemory(habits=["habit1", "habit2"])
    vector_store = FakeVectorStore(search_results=["case1"])
    result = retrieve_context(state, memory, vector_store, provider=None)
    assert result["context"]["habits"] == ["habit1", "habit2"]
    assert result["context"]["similar_cases"] == ["case1"]


def test_retrieve_context_empty_habits_not_included() -> None:
    state = {"task": "t"}
    memory = FakeMemory(habits=[])
    result = retrieve_context(state, memory, vector_store=None, provider=None)
    assert "habits" not in result["context"]


def test_retrieve_context_memory_exception_is_swallowed() -> None:
    state = {"task": "t"}
    memory = FakeMemory(raises=True)
    result = retrieve_context(state, memory, vector_store=None, provider=None)
    assert result["context"] == {}


def test_retrieve_context_vector_store_exception_is_swallowed() -> None:
    state = {"task": "t"}
    vector_store = FakeVectorStore(raises_on_search=True)
    result = retrieve_context(state, memory=None, vector_store=vector_store, provider=None)
    assert result["context"] == {}


def test_retrieve_context_none_sources_gives_empty_context() -> None:
    state = {"task": "t"}
    result = retrieve_context(state, memory=None, vector_store=None, provider=None)
    assert result["context"] == {}


# ---------------------------------------------------------------------------
# query_model
# ---------------------------------------------------------------------------


def test_query_model_unknown_agent_sets_error() -> None:
    state = {"agent_key": "inconnu", "task": "faire un truc"}
    result = query_model(state, provider=None, agents={}, toolbox=None, model_selector=lambda *a: "m")
    assert "introuvable" in result["error"]
    assert "inconnu" in result["response"]


def test_query_model_empty_task_sets_error() -> None:
    agent = FakeAgentWithRun()
    state = {"agent_key": "dev", "task": ""}
    result = query_model(state, provider=None, agents={"dev": agent}, toolbox=None, model_selector=lambda *a: "m")
    assert result["error"] == "Tâche vide — rien à exécuter"


def test_query_model_uses_run_when_available() -> None:
    agent = FakeAgentWithRun(result={"response": "réponse via run", "suggested_skill": "skill-x"})
    state = {"agent_key": "dev", "task": "fait un truc"}
    result = query_model(state, provider=None, agents={"dev": agent}, toolbox=None, model_selector=lambda *a: "modelX")
    assert result["response"] == "réponse via run"
    assert result["suggested_skill"] == "skill-x"
    assert result["model"] == "modelX"
    assert agent.last_call is not None
    assert agent.last_call["model"] == "modelX"


def test_query_model_uses_query_when_no_run() -> None:
    agent = FakeAgentWithQuery(result={"response": "réponse via query"})
    state = {"agent_key": "dev", "task": "fait un truc"}
    result = query_model(state, provider=None, agents={"dev": agent}, toolbox=None, model_selector=lambda *a: "m")
    assert result["response"] == "réponse via query"
    assert agent.last_call is not None


def test_query_model_bare_agent_uses_str_fallback() -> None:
    agent = FakeAgentBare()
    state = {"agent_key": "dev", "task": "fait un truc"}
    result = query_model(state, provider=None, agents={"dev": agent}, toolbox=None, model_selector=lambda *a: "m")
    assert result["response"] == "agent-bare"


def test_query_model_non_dict_result_stringified() -> None:
    agent = FakeAgentWithRun(result=42)
    state = {"agent_key": "dev", "task": "fait un truc"}
    result = query_model(state, provider=None, agents={"dev": agent}, toolbox=None, model_selector=lambda *a: "m")
    assert result["response"] == "42"


def test_query_model_builds_context_string_in_prompt() -> None:
    agent = FakeAgentWithRun(result={"response": "ok"})
    state = {"agent_key": "dev", "task": "la tâche", "context": {"habits": ["h1"]}}
    query_model(state, provider=None, agents={"dev": agent}, toolbox=None, model_selector=lambda *a: "m")
    assert "Contexte:" in agent.last_call["prompt"]
    assert "la tâche" in agent.last_call["prompt"]


def test_query_model_toolbox_auto_execute_populates_context() -> None:
    agent = FakeAgentWithRun(result={"response": "ok"})
    toolbox = FakeToolbox(result={"tool": "result"})
    state = {"agent_key": "dev", "task": "la tâche"}
    query_model(state, provider=None, agents={"dev": agent}, toolbox=toolbox, model_selector=lambda *a: "m")
    assert toolbox.called_with == "la tâche"
    assert agent.last_call["context"]["tool_results"] == {"tool": "result"}


def test_query_model_toolbox_exception_is_swallowed() -> None:
    agent = FakeAgentWithRun(result={"response": "ok"})
    toolbox = FakeToolbox(raises=True)
    state = {"agent_key": "dev", "task": "la tâche"}
    result = query_model(state, provider=None, agents={"dev": agent}, toolbox=toolbox, model_selector=lambda *a: "m")
    assert "error" not in result
    assert agent.last_call["context"]["tool_results"] == {}


def test_query_model_agent_run_exception_sets_error() -> None:
    agent = FakeAgentWithRun(raises=True)
    state = {"agent_key": "dev", "task": "la tâche"}
    result = query_model(state, provider=None, agents={"dev": agent}, toolbox=None, model_selector=lambda *a: "m")
    assert result["error"] == "agent en erreur"
    assert "erreur est survenue" in result["response"]


# ---------------------------------------------------------------------------
# save_results
# ---------------------------------------------------------------------------


def test_save_results_empty_response_short_circuits() -> None:
    state: dict[str, Any] = {}
    result = save_results(state, memory=None, vector_store=None)
    assert result is state


def test_save_results_indexes_response_in_vector_store() -> None:
    state = {"response": "une réponse"}
    vector_store = FakeVectorStore()
    save_results(state, memory=None, vector_store=vector_store)
    assert vector_store.indexed == [("une réponse", {"source": "agent_response"})]


def test_save_results_vector_store_exception_is_swallowed() -> None:
    state = {"response": "une réponse"}
    vector_store = FakeVectorStore(raises_on_index=True)
    result = save_results(state, memory=None, vector_store=vector_store)
    assert result is state  # pas d'exception propagée


def test_save_results_no_vector_store_is_noop() -> None:
    state = {"response": "une réponse"}
    result = save_results(state, memory=None, vector_store=None)
    assert result is state


# ---------------------------------------------------------------------------
# format_output
# ---------------------------------------------------------------------------


def test_format_output_full_state() -> None:
    state = {
        "response": "réponse finale",
        "agent_key": "dev",
        "model": "qwen2.5",
        "backend": "vllm",
        "error": None,
        "suggested_skill": "skill-a",
        "context": {"habits": ["h1"]},
    }
    result = format_output(state)
    assert result == {
        "response": "réponse finale",
        "agent": "dev",
        "model": "qwen2.5",
        "backend": "vllm",
        "error": None,
        "suggested_skill": "skill-a",
        "context": {"habits": ["h1"]},
    }


def test_format_output_defaults_on_empty_state() -> None:
    result = format_output({})
    assert result == {
        "response": "",
        "agent": "",
        "model": "",
        "backend": "ollama",
        "error": None,
        "suggested_skill": None,
        "context": {},
    }


# ---------------------------------------------------------------------------
# Helpers privés de retry (utilisés par pipeline.py)
# ---------------------------------------------------------------------------


def test_should_retry_true_when_on_error_retry_and_attempts_remaining() -> None:
    step = FakeStep(on_error="retry")
    assert _should_retry(step, attempt=0, max_retries=3) is True


def test_should_retry_false_when_on_error_not_retry() -> None:
    step = FakeStep(on_error="stop")
    assert _should_retry(step, attempt=0, max_retries=3) is False


def test_should_retry_false_when_attempts_exhausted() -> None:
    step = FakeStep(on_error="retry")
    assert _should_retry(step, attempt=3, max_retries=3) is False


def test_wait_before_retry_sleeps_proportional_to_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr("services.pipeline_steps.time.sleep", lambda d: sleep_calls.append(d))
    _wait_before_retry(attempt=2, max_retries=5, step_name="s1")
    assert sleep_calls == [RETRY_DELAY * 3]


def test_runner_supports_model_true_for_three_params() -> None:
    def runner(agent_key: str, prompt: str, model: str | None = None) -> str:
        return "ok"

    assert _runner_supports_model(runner) is True


def test_runner_supports_model_false_for_two_params() -> None:
    def runner(agent_key: str, prompt: str) -> str:
        return "ok"

    assert _runner_supports_model(runner) is False


def test_runner_supports_model_false_when_signature_unavailable() -> None:
    # Un objet non introspectable (pas de __call__ standard) → ValueError/TypeError avalé
    assert _runner_supports_model(42) is False


def test_non_callable_runner_error_is_exception() -> None:
    with pytest.raises(NonCallableRunnerError):
        raise NonCallableRunnerError("runner non callable")


def test_max_error_length_constant_value() -> None:
    assert MAX_ERROR_LENGTH == 200
