"""Tests MT-KB-L2x — ``chunk_ids`` dans la réponse chat (fermeture ADR-008).

Unit : helper ``_attach_chunk_ids`` ; intégration : route POST /api/jarvis
avec un orchestrateur factice retournant ``context.similar_cases``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app
from controllers.routes.jarvis import _attach_chunk_ids


class _ContextOrchestrator:
    """Orchestrateur factice : réponse avec contexte contenant des chunks."""

    async def handle_request(self, task: str, image: str | None = None, conv_id: str | None = None) -> dict:
        return {
            "response": "ok",
            "agent": "dev",
            "model": "fake",
            "context": {
                "similar_cases": [
                    {"text": "a", "metadata": {"chunk_id": "X-4:0"}},
                    {"text": "b", "metadata": {"chunk_id": "X-4:1"}},
                    {"text": "c", "metadata": {}},
                ]
            },
        }


class _Analytics:
    def track_query(self, **_: object) -> None:
        return None


class _Conversations:
    def add_message(self, *args: object, **kwargs: object) -> None:
        return None


def test_attach_chunk_ids_extracts_chunk_ids() -> None:
    result = {
        "response": "ok",
        "context": {
            "similar_cases": [
                {"text": "a", "metadata": {"chunk_id": "X-4:0"}},
                {"text": "b", "metadata": {"chunk_id": "X-4:1"}},
                {"text": "c", "metadata": {}},
            ]
        },
    }
    out = _attach_chunk_ids(result)
    assert out["chunk_ids"] == ["X-4:0", "X-4:1"]


def test_attach_chunk_ids_empty_without_context() -> None:
    out = _attach_chunk_ids({"response": "ok"})
    assert out["chunk_ids"] == []


def test_chat_response_includes_chunk_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("controllers.routes.jarvis.read_preferences", lambda: {})
    app = create_app()
    app.state.context = SimpleNamespace(
        orchestrator=_ContextOrchestrator(),
        analytics=_Analytics(),
        conversations=_Conversations(),
        inference=None,
    )
    resp = TestClient(app).post("/api/jarvis", json={"task": "@dev something"})
    assert resp.status_code == 200
    assert resp.json()["chunk_ids"] == ["X-4:0", "X-4:1"]
