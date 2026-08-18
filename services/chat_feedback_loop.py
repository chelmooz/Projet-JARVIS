"""ChatFeedbackLoop — ADR-008 loop on chat path (trace + judge + update_score).

Runs as a background task after successful chat response.
Fail-open: never blocks the response, logs errors silently.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Protocol

from services.adapters.protocols import IResponseJudge, TraceRecord
from services.vector import VectorService

_logger = logging.getLogger("jarvis.chat_feedback_loop")


class ITraceStore(Protocol):
    """Port for trace persistence (sidecar JSONL)."""

    def append(self, record: TraceRecord) -> None: ...


class ChatFeedbackLoop:
    """Background feedback loop for chat responses.

    After a successful chat response:
    1. Extract chunks from result["context"]["similar_cases"]
    2. Call judge to evaluate (query, chunks, response)
    3. Write trace record to sidecar
    4. Call vector.update_score on each chunk_id with the judge score
    """

    def __init__(
        self,
        judge: IResponseJudge,
        trace_store: ITraceStore,
        vector_service: VectorService,
    ) -> None:
        self._judge = judge
        self._trace_store = trace_store
        self._vector = vector_service

    def schedule(
        self,
        task: str,
        similar_cases: list[dict[str, Any]],
        response: str,
        agent: str,
        model: str,
    ) -> None:
        """Schedule the feedback loop as a background task (fire-and-forget).

        Does not await — response is already returned to user.
        Fail-open: any exception is logged, never propagated.
        """
        asyncio.create_task(
            self._run_feedback_loop(task, similar_cases, response, agent, model)
        )

    async def _run_feedback_loop(
        self,
        task: str,
        similar_cases: list[dict[str, Any]],
        response: str,
        agent: str,
        model: str,
    ) -> None:
        """Execute the feedback loop: judge → trace → update_score."""
        try:
            # Extract chunk texts and IDs
            chunk_texts = []
            chunk_ids = []
            for case in similar_cases:
                text = case.get("text", "")
                metadata = case.get("metadata", {})
                chunk_id = metadata.get("chunk_id")
                if text and chunk_id:
                    chunk_texts.append(text)
                    chunk_ids.append(chunk_id)

            if not chunk_texts or not chunk_ids:
                _logger.debug("No valid chunks for feedback loop, skipping")
                return

            # 1. Judge evaluation
            judge_result = self._judge.evaluate(task, chunk_texts, response)
            judge_score = float(judge_result.get("score", 0.0))
            judge_reason = str(judge_result.get("reason", ""))

            # 2. Trace record
            trace = TraceRecord(
                trace_id=str(uuid.uuid4())[:8],
                pipeline_id=f"chat-{agent}-{uuid.uuid4().hex[:8]}",
                query=task,
                retrieved_chunk_ids=chunk_ids,
                judge_score=judge_score,
                judge_reason=judge_reason,
                timestamp=datetime.now().isoformat(),
                feedback=None,  # No explicit feedback in chat path
                status="completed",
            )
            self._trace_store.append(trace)

            # 3. Update scores on chunks
            for chunk_id in chunk_ids:
                self._vector.update_score(chunk_id, judge_score)

            _logger.info(
                "Chat feedback loop completed: agent=%s, chunks=%d, score=%.3f",
                agent,
                len(chunk_ids),
                judge_score,
            )

        except Exception as e:
            # Fail-open: log and continue, never block the chat response
            _logger.warning("Chat feedback loop failed (fail-open): %s", e)