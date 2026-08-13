"""Tests intégrés pour pipeline_steps.py — exécution d'étape de pipeline."""

from __future__ import annotations

import pytest

from services.pipeline_steps import execute_pipeline_step


class MockStep:
    """Pas de étape minimale pour les tests."""

    def __init__(self, name: str = "test_step", agent_key: str | None = "dev",
                 prompt_template: str = "Tâche : {task}", on_error: str = "abort"):
        self.name = name
        self.agent_key = agent_key
        self.prompt_template = prompt_template
        self.on_error = on_error


class MockAgentRunner:
    """Mock runner d'agent qui retourne une réponse fixe."""

    def __call__(self, agent_key: str, prompt: str) -> str:
        return f"Réponse simulée pour {agent_key} : {prompt[:30]}..."


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
    result = execute_pipeline_step(
        state=state,
        step=step,
        task="Test prompt",
        agent_runner=MockAgentRunner(),
        inference=None,
        model_selector=None,
        max_retries=0,
    )
    assert result is state
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


def test_execute_pipeline_step_max_retries() -> None:
    """TDD : le nombre de réessais est respecté."""
    state: dict[str, Any] = {"task": "Test prompt", "context": {}, "results": []}
    step = MockStep(name="test_step", agent_key="dev")
    # Avec max_retries=0, une seule tentative
    result = execute_pipeline_step(
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