"""Tests MT 7.1 — Capitalisation post-pipeline.

Vérifie que PipelineService appelle ITraceStore.append() après exécution réussie,
et qu'il fonctionne toujours sans trace_store (backward compat).
"""

import pytest
from unittest.mock import MagicMock

from models import Pipeline, PipeStep
from services.adapters.protocols import ITraceStore, TraceRecord
from services.pipeline import PipelineService


@pytest.fixture
def mock_trace_store():
    """Mock de ITraceStore pour isoler le test."""
    store = MagicMock(spec=ITraceStore)
    store.append = MagicMock()
    return store


@pytest.fixture
def simple_pipeline():
    """Pipeline minimal avec une seule étape."""
    return Pipeline(
        id="test_pipeline",
        steps=[PipeStep(name="step1", agent_key="agent1", prompt_template="Task: {task}")],
        on_error="abort",
    )


@pytest.fixture
def mock_agent_runner():
    """Agent runner mocké pour éviter un vrai appel LLM."""
    def runner(agent_key: str, prompt: str, model: str | None = None) -> str:
        return f"Response from {agent_key}"
    return runner


def test_pipeline_capitalizes_trace_on_success(
    mock_trace_store, simple_pipeline, mock_agent_runner
):
    """RED→GREEN : Le pipeline doit appeler trace_store.append() après succès."""
    # ARRANGE
    pipeline_service = PipelineService(
        agent_runner=mock_agent_runner,
        trace_store=mock_trace_store,
    )
    pipeline_service.register(simple_pipeline)

    # ACT
    result = pipeline_service.run(
        pipeline_id="test_pipeline",
        task="Test diagnostic task",
        context={}
    )

    # ASSERT — le pipeline a réussi
    assert result["error"] is None
    assert result["steps"] == 1

    # ASSERT — le store a été appelé exactement une fois
    mock_trace_store.append.assert_called_once()

    # ASSERT — l'argument est un TraceRecord valide
    call_args = mock_trace_store.append.call_args[0][0]
    assert isinstance(call_args, TraceRecord)
    assert call_args.pipeline_id == "test_pipeline"
    assert call_args.query == "Test diagnostic task"
    assert call_args.retrieved_chunk_ids == []  # MT 7.2 pas encore implémenté
    assert call_args.judge_score == 0.0  # MT 7.3 pas encore implémenté
    assert call_args.judge_reason == ""


def test_pipeline_works_without_trace_store(simple_pipeline, mock_agent_runner):
    """Non-régression : le pipeline fonctionne sans trace_store (backward compat)."""
    # ARRANGE — pas de trace_store injecté
    pipeline_service = PipelineService(
        agent_runner=mock_agent_runner,
        # trace_store=None par défaut
    )
    pipeline_service.register(simple_pipeline)

    # ACT
    result = pipeline_service.run(
        pipeline_id="test_pipeline",
        task="Test task",
        context={}
    )

    # ASSERT — le pipeline réussit normalement
    assert result["error"] is None
    assert result["steps"] == 1
    assert result["results"][0]["response"] == "Response from agent1"