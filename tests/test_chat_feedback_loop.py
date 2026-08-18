"""Tests for ChatFeedbackLoop — ADR-008 loop on chat path (trace + judge + update_score)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class FakeTraceStore:
    """Fake trace store capturing appended records."""

    def __init__(self) -> None:
        self.records: list[Any] = []

    def append(self, record: Any) -> None:
        self.records.append(record)


class FakeJudge:
    """Fake judge returning a fixed score."""

    def __init__(self, score: float = 0.75, reason: str = "good") -> None:
        self.score = score
        self.reason = reason
        self.calls: list[tuple[str, list[str], str]] = []
        self.should_raise = False

    def evaluate(self, query: str, chunks: list[str], response: str) -> dict[str, Any]:
        self.calls.append((query, chunks, response))
        if self.should_raise:
            raise RuntimeError("Judge failed")
        return {"score": self.score, "reason": self.reason}


class FakeVectorService:
    """Fake vector service with spy on update_score."""

    def __init__(self) -> None:
        self.update_score_calls: list[tuple[str, float]] = []
        self.search_results: list[dict[str, Any]] = []

    def update_score(self, chunk_id: str, delta: float) -> int:
        self.update_score_calls.append((chunk_id, delta))
        return 1

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self.search_results


class FakeInference:
    """Fake inference service."""

    def __init__(self) -> None:
        self._adapter = MagicMock()

    def _adapter(self) -> Any:
        return self._adapter

    def is_healthy(self) -> bool:
        return True


class FakeMemory:
    def get_habits(self) -> list[dict[str, Any]]:
        return []

    def update_habits(self, entry: dict[str, Any]) -> None:
        pass


class FakeLog:
    def log(self, level: str, message: str) -> None:
        pass


class FakeAnalytics:
    def track_query(self, **kwargs: Any) -> None:
        pass

    def get_stats(self) -> dict[str, Any]:
        return {}

    def get_most_used(self) -> dict[str, Any]:
        return {}


class FakeConversations:
    def create(self, title: str = "Nouvelle conversation") -> str:
        return "conv-123"

    def add_message(self, **kwargs: Any) -> None:
        pass


class FakeMetrics:
    def incr_requests(self, endpoint: str = "/api/jarvis") -> None:
        pass


class FakeRouter:
    def select_agent(self, task: str) -> str:
        return "dev"


class FakeToolbox:
    pass


class FakeAgent:
    """Fake agent for testing."""

    def __init__(self, response: str = "test response") -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((task, model, context))
        return {"response": self.response}


class FakeAgentGraph:
    """Fake agent graph for testing."""

    def __init__(
        self,
        response: str = "test response",
        agent_key: str = "dev",
        model: str = "test-model",
        similar_cases: list[dict[str, Any]] | None = None,
    ) -> None:
        self.response = response
        self.agent_key = agent_key
        self.model = model
        self.similar_cases = similar_cases or [
            {"text": "chunk 1", "metadata": {"chunk_id": "chunk-1"}},
            {"text": "chunk 2", "metadata": {"chunk_id": "chunk-2"}},
        ]

    async def run(
        self, task: str, image: str | None = None, conversation_id: str | None = None
    ) -> dict[str, Any]:
        return {
            "response": self.response,
            "agent": self.agent_key,
            "model": self.model,
            "context": {"similar_cases": self.similar_cases},
        }


@pytest.fixture
def setup_services() -> dict[str, Any]:
    """Create all fake services needed for OrchestratorService."""
    from services.orchestrator import OrchestratorService

    inference = FakeInference()
    memory = FakeMemory()
    vector = FakeVectorService()
    log = FakeLog()
    analytics = FakeAnalytics()
    conversations = FakeConversations()
    metrics = FakeMetrics()
    agents = {"dev": FakeAgent()}
    router = FakeRouter()
    toolbox = FakeToolbox()

    # Factory for agent graph
    def agent_graph_factory() -> FakeAgentGraph:
        return FakeAgentGraph()

    orchestrator = OrchestratorService(
        inference=inference,
        memory=memory,
        vector=vector,
        log=log,
        analytics=analytics,
        conversations=conversations,
        metrics=metrics,
        agents=agents,
        router_service=router,
        toolbox=toolbox,
        agent_graph_factory=agent_graph_factory,
    )

    return {
        "orchestrator": orchestrator,
        "vector": vector,
        "inference": inference,
    }


@pytest.mark.asyncio
async def test_chat_triggers_trace_judge_update_score(setup_services: dict[str, Any]) -> None:
    """After _handle_text, trace written with chunks, judge called, update_score on chunk ids."""
    from services.chat_feedback_loop import ChatFeedbackLoop
    from services.adapters.protocols import TraceRecord

    services = setup_services
    orchestrator = services["orchestrator"]
    vector = services["vector"]

    # Setup fake judge and trace store
    fake_judge = FakeJudge(score=0.8, reason="relevant")
    fake_trace_store = FakeTraceStore()

    # Create feedback loop
    feedback_loop = ChatFeedbackLoop(
        judge=fake_judge,
        trace_store=fake_trace_store,
        vector_service=vector,
    )

    # Inject feedback loop into orchestrator
    orchestrator.feedback_loop = feedback_loop

    # Execute a chat request
    result = await orchestrator.handle_request("test query", image=None, conv_id="test-conv")

    # Verify response is returned
    assert result["response"] == "test response"
    assert result["agent"] == "dev"

    # Verify trace was written
    assert len(fake_trace_store.records) == 1
    trace = fake_trace_store.records[0]
    assert isinstance(trace, TraceRecord)
    assert trace.query == "test query"
    assert trace.retrieved_chunk_ids == ["chunk-1", "chunk-2"]
    assert trace.judge_score == 0.8
    assert trace.judge_reason == "relevant"
    assert trace.status == "completed"

    # Verify judge was called with correct args
    assert len(fake_judge.calls) == 1
    query, chunks, response = fake_judge.calls[0]
    assert query == "test query"
    assert chunks == ["chunk 1", "chunk 2"]
    assert response == "test response"

    # Verify update_score was called on each chunk id
    assert len(vector.update_score_calls) == 2
    assert ("chunk-1", 0.8) in vector.update_score_calls
    assert ("chunk-2", 0.8) in vector.update_score_calls


@pytest.mark.asyncio
async def test_chat_loop_fail_open_judge_error(setup_services: dict[str, Any]) -> None:
    """Judge raises → response still returned, no exception, no update_score."""
    from services.chat_feedback_loop import ChatFeedbackLoop

    services = setup_services
    orchestrator = services["orchestrator"]
    vector = services["vector"]

    fake_judge = FakeJudge()
    fake_judge.should_raise = True
    fake_trace_store = FakeTraceStore()

    feedback_loop = ChatFeedbackLoop(
        judge=fake_judge,
        trace_store=fake_trace_store,
        vector_service=vector,
    )
    orchestrator.feedback_loop = feedback_loop

    # Should not raise
    result = await orchestrator.handle_request("test query", image=None, conv_id="test-conv")

    assert result["response"] == "test response"
    assert len(fake_trace_store.records) == 0  # No trace if judge fails
    assert len(vector.update_score_calls) == 0  # No update_score if judge fails


@pytest.mark.asyncio
async def test_chat_not_blocked_by_loop(setup_services: dict[str, Any]) -> None:
    """Response returned even if loop is slow/failing (background task, not awaited before return)."""
    from services.chat_feedback_loop import ChatFeedbackLoop

    services = setup_services
    orchestrator = services["orchestrator"]
    vector = services["vector"]

    # Make judge slow
    fake_judge = FakeJudge()

    async def slow_evaluate(query: str, chunks: list[str], response: str) -> dict[str, Any]:
        await asyncio.sleep(0.5)  # Simulate slow judge
        return {"score": 0.5, "reason": "slow"}

    fake_judge.evaluate = slow_evaluate
    fake_trace_store = FakeTraceStore()

    feedback_loop = ChatFeedbackLoop(
        judge=fake_judge,
        trace_store=fake_trace_store,
        vector_service=vector,
    )
    orchestrator.feedback_loop = feedback_loop

    # Should return quickly (not wait for the slow background task)
    import time
    start = time.time()
    result = await orchestrator.handle_request("test query", image=None, conv_id="test-conv")
    elapsed = time.time() - start

    assert result["response"] == "test response"
    # Response should come back fast (< 0.3s), not wait for 0.5s judge
    assert elapsed < 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])