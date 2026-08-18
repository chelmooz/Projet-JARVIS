"""Tests MT-KB-L3z-ter — ``id`` du message assistant dans la réponse /api/jarvis.

Couvre le bug de production : les pouces 👍/👎 n'apparaissent pas car la
réponse ne contient aucun ``id`` de message (chat.js n'attache le feedback
que si ``meta.id`` / ``data.id`` est présent).

- Chemin JSON : POST /api/jarvis -> réponse contenant ``id`` égal à l'id du
  message assistant réellement persisté dans le store conversation.
- Chemin SSE : l'événement ``done`` (meta) contient le même ``id``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app
from services.conversation import ConversationService


class _FakeOrchestrator:
    """Orchestrateur factice : réponse déterministe, pas de vrai LLM."""

    async def handle_request(self, task: str, image: str | None = None, conv_id: str | None = None) -> dict[str, Any]:
        del task, image, conv_id
        return {"response": "réponse de test", "agent": "dev", "model": "fake"}


class _Analytics:
    def track_query(self, **_: object) -> None:
        return None


class _StreamCapableInference:
    """Double minimal exposant l'API de streaming utilisée par la route SSE."""

    def set_stream_sink(self, sink: Any) -> None:
        self.sink_set = True

    def clear_stream_sink(self) -> None:
        self.sink_cleared = True


def _build_client(
    monkeypatch: pytest.MonkeyPatch, conversations: ConversationService, inference: Any = None
) -> TestClient:
    monkeypatch.setattr("controllers.routes.jarvis.read_preferences", lambda: {})
    app = create_app()
    app.state.context = SimpleNamespace(
        orchestrator=_FakeOrchestrator(),
        analytics=_Analytics(),
        conversations=conversations,
        inference=inference,
    )
    return TestClient(app)


def _assistant_message_id(conv_svc: ConversationService, conv_id: str) -> str:
    """Id du dernier message assistant persisté dans le store conversation."""
    conv = conv_svc.get_conversation(conv_id)
    assert conv is not None
    assistants = [m for m in conv["messages"] if m["role"] == "assistant"]
    assert len(assistants) == 1
    assert assistants[-1]["id"]
    return str(assistants[-1]["id"])


def _parse_done_id(raw: str) -> str:
    """Extrait l'id du payload de l'événement SSE ``done``."""
    for frame in raw.split("\n\n"):
        if "event: done" not in frame:
            continue
        data = "".join(line[5:].strip() for line in frame.split("\n") if line.startswith("data:"))
        payload = json.loads(data)
        return str(payload["id"])
    raise AssertionError("événement done absent du flux SSE")


class TestChatResponseIncludesMessageId:
    def test_json_response_includes_saved_assistant_message_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """POST /api/jarvis -> réponse contenant l'id du message assistant persisté."""
        conv_svc = ConversationService(storage_dir=str(tmp_path))
        client = _build_client(monkeypatch, conv_svc)

        resp = client.post("/api/jarvis", json={"task": "hello", "conversation_id": "conv-123"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"]
        assert body["id"] == _assistant_message_id(conv_svc, "conv-123")

    def test_sse_done_event_includes_saved_assistant_message_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """Chemin SSE : l'événement ``done`` (meta) porte l'id du message persisté."""
        conv_svc = ConversationService(storage_dir=str(tmp_path))
        inference = _StreamCapableInference()
        client = _build_client(monkeypatch, conv_svc, inference=inference)

        with client.stream(
            "POST",
            "/api/jarvis",
            json={"task": "hello", "conversation_id": "conv-456"},
            headers={"accept": "text/event-stream"},
        ) as resp:
            assert resp.status_code == 200
            raw = "".join(resp.iter_text())

        assert _parse_done_id(raw) == _assistant_message_id(conv_svc, "conv-456")
