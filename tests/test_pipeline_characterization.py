#!/usr/bin/env python3
"""Caractérisation des chemins agent_runner dans PipelineService."""
from __future__ import annotations

from typing import Any

from models import OnError, Pipeline, PipeStep
from services.pipeline import PipelineService


class MockRunner:
    """Runner factice qui retourne une réponse moke."""
    def __call__(self, agent_key: str, prompt: str, model: str | None = None) -> str:
        return "mocked"


def test_pipeline_with_agent_runner_callable() -> None:
    """Caractérisation : runner callable exécuté avec agent_key et prompt."""
    service = PipelineService(
        agent_runner=MockRunner(),
        inference=None,
        model_selector=None,
    )
    service.register(
        Pipeline(
            id="p",
            steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),),
        )
    )
    result = service.run("p", "tester")
    assert result["error"] is None
    # Le runner a été appelé et a produit une réponse moke
    assert result["results"][-1]["response"] == "mocked"


def test_pipeline_with_agent_runner_non_callable() -> None:
    """Caractérisation : runner non callable entraîne NonCallableRunnerError."""
    service = PipelineService(
        agent_runner="not-a-callable",  # type: ignore
        inference=None,
        model_selector=None,
    )
    service.register(
        Pipeline(
            id="p",
            steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),),
        )
    )
    result = service.run("p", "tester")
    assert result["error"] is not None
    # L'erreur doit mentionner le problème d'agent_runner
    error_msg = result["results"][-1]["error"]
    assert "agent_runner" in error_msg.lower() or "NonCallableRunnerError" in error_msg


def test_pipeline_agent_key_without_runner_raises() -> None:
    """Caractérisation : sans agent_runner, pipeline avec agent_key lève erreur."""
    service = PipelineService(
        inference=None,
        model_selector=None,
    )
    service.register(
        Pipeline(
            id="p",
            steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),),
        )
    )
    result = service.run("p", "tester")
    # Sans agent_runner et sans inference, l'erreur est enregistrée dans results
    assert result["error"] is not None
    assert "agent_runner" in result["error"].lower() or result["results"][-1]["error"] is not None


def test_pipeline_runner_with_model_selector() -> None:
    """Caractérisation : runner appelé avec modèle sélectionné par model_selector."""
    runner_instance = None

    class ThreeParamRunner:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str | None]] = []

        def __call__(self, agent_key: str, prompt: str, model: str | None = None) -> str:
            self.calls.append((agent_key, prompt, model))
            return f"ok-{agent_key}-{model or 'none'}"

    def model_selector(agent_key: str, inference: Any) -> str:
        return "qwen2.5-selected"

    service = PipelineService(
        agent_runner=ThreeParamRunner(),
        inference=None,
        model_selector=model_selector,
    )
    service.register(
        Pipeline(
            id="p",
            steps=(PipeStep(name="s1", agent_key="dev", prompt_template="{task}"),),
        )
    )
    result = service.run("p", "tester")
    assert result["error"] is None
    assert len(service._agent_runner.calls) == 1
    assert "qwen" in service._agent_runner.calls[0][2].lower()