"""Tests intégrés pour pipeline_steps.py — exécution d'étape de pipeline."""

from __future__ import annotations

from typing import Any

from services.pipeline_steps import execute_pipeline_step


class MockStep:
    """Pas de étape minimale pour les tests."""

    def __init__(
        self,
        name: str = "test_step",
        agent_key: str | None = "dev",
        prompt_template: str = "Tâche : {task}",
        on_error: str = "abort",
    ):
        self.name = name
        self.agent_key = agent_key
        self.prompt_template = prompt_template
        self.on_error = on_error


class MockAgentRunner:
    """Mock runner d'agent qui retourne une réponse fixe."""

    def __call__(self, agent_key: str, prompt: str) -> str:
        return f"Réponse simulée pour {agent_key} : {prompt[:30]}..."


class MockAgentRunnerThreeParams:
    """Runner d'agent acceptant un 3e argument ``model``."""

    def __call__(self, agent_key: str, prompt: str, model: str | None) -> str:
        return f"Runner3 [{agent_key}] model={model} : {prompt[:30]}..."


class MockInference:
    """Mock service d'inférence qui retourne une réponse fixe."""

    def query(self, prompt: str, model: str | None = None) -> str:
        return f"Réponse d'inférence pour : {prompt[:30]}..."

    def __call__(self, prompt: str, model: str | None = None) -> str:
        return self.query(prompt, model)


def test_execute_pipeline_step_with_agent_runner() -> None:
    """TDD : exécuter une étape avec un agent_runner doit mettre à jour l'état."""
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev")
    execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=MockAgentRunner(),
        inference=None,
        model_selector=None,
        max_retries=0,
    )
    assert state is not None  # execute_pipeline_step returns the state dict
    assert state["results"][-1]["step"] == "test_step"
    assert "Réponse simulée" in state["results"][-1]["response"]


def test_execute_pipeline_step_with_inference() -> None:
    """TDD : exécuter une étape avec inference doit mettre à jour l'état."""
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev")
    result = execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=None,
        inference=MockInference(),
        model_selector=None,
        max_retries=0,
    )
    assert result is state
    assert state["results"][-1]["step"] == "test_step"
    assert "Réponse d'inférence" in state["results"][-1]["response"]


def test_execute_pipeline_step_runner_three_params_receives_model() -> None:
    """TDD : un runner à 3 params reçoit le modèle sélectionné (parité _run_via_agent)."""
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev")
    result = execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=MockAgentRunnerThreeParams(),
        inference=None,
        model_selector=lambda agent_key, inference: "qwen2.5-selected",
        max_retries=0,
    )
    assert result is state
    assert "model=qwen2.5-selected" in state["results"][-1]["response"]


def test_execute_pipeline_step_runner_two_params_without_model() -> None:
    """TDD : un runner à 2 params est appelé sans modèle (parité _run_via_agent)."""
    calls: list[tuple[str, str]] = []
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev")

    def runner(agent_key: str, prompt: str) -> str:
        calls.append((agent_key, prompt))
        return "Réponse simulée"

    execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=runner,
        inference=None,
        model_selector=lambda agent_key, inference: "qwen2.5-selected",
        max_retries=0,
    )
    assert len(calls) == 1
    assert len(calls[0]) == 2


class CountingRunner:
    """Runner qui échoue toujours, avec compteur d'appels."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, agent_key: str, prompt: str) -> str:
        self.calls += 1
        raise RuntimeError("boom")


def test_execute_pipeline_step_retry_conditionnel_retry(monkeypatch: Any) -> None:
    """Parité production : on_error="retry" réessaie jusqu'à max_retries."""
    monkeypatch.setattr("services.pipeline_steps.time.sleep", lambda _: None)
    runner = CountingRunner()
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev", on_error="retry")
    execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=runner,
        inference=None,
        model_selector=None,
        max_retries=2,
    )
    assert runner.calls == 3  # 1 tentative + 2 retries
    assert state["results"][-1]["error"]


def test_execute_pipeline_step_retry_conditionnel_abort(monkeypatch: Any) -> None:
    """Parité production : on_error="abort" → pas de retry, une seule tentative."""
    monkeypatch.setattr("services.pipeline_steps.time.sleep", lambda _: None)
    runner = CountingRunner()
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev", on_error="abort")
    execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=runner,
        inference=None,
        model_selector=None,
        max_retries=2,
    )
    assert runner.calls == 1
    assert state["results"][-1]["error"]


def test_execute_pipeline_step_non_callable_runner() -> None:
    """TDD : un agent_runner non callable produit une erreur typée, pas un repr."""
    from services.pipeline_steps import NonCallableRunnerError

    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev")
    execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner="not-a-callable",
        inference=None,
        model_selector=None,
        max_retries=0,
    )
    assert state["error"] == str(NonCallableRunnerError("agent_runner non callable : 'not-a-callable'"))
    assert state["results"][-1]["response"] is None
    assert state["results"][-1]["error"]  # erreur d'entrée, pas un repr de succès


def test_execute_pipeline_step_max_retries() -> None:
    """TDD : le nombre de réessais est respecté."""
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev")
    # Avec max_retries=0, une seule tentative
    execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=None,
        inference=None,  # Aucun des deux -> erreur
        model_selector=None,
        max_retries=0,
    )
    assert "error" in state
    assert "Aucun agent_runner ni inference configuré" in state["error"]
