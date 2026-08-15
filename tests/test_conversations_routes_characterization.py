"""Tests de caractérisation pour ``controllers.routes.conversations`` (Lot 7).

CRUD conversations + feedback explicite/implicite (44% avant ce fichier).
DI via ``app.state.context`` (``SimpleNamespace``), pattern identique à
``tests/test_api_rag.py``. Doubles de test locaux (``_FakeConversations``,
``_FakeVectorFeedback``) car ``FakeVector``/``FakeConversations`` du
``conftest.py`` partagé ne couvrent pas ``adjust_weight`` (hors ``VectorPort``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app


class _FakeConversations:
    """Double minimal de ``ConversationService`` : CRUD en mémoire."""

    def __init__(self) -> None:
        self._convs: dict[str, dict[str, Any]] = {}
        self._counter = 0
        self.deleted: list[str] = []
        self.delete_all_called = False
        self.add_message_calls: list[tuple[str, str, str]] = []
        self.raise_on_add_message: Exception | None = None

    def create(self, title: str = "Nouvelle conversation") -> str:
        self._counter += 1
        conv_id = f"conv-{self._counter}"
        self._convs[conv_id] = {"id": conv_id, "title": title, "messages": []}
        return conv_id

    def add_message(self, conv_id: str, role: str, content: str) -> None:
        self.add_message_calls.append((conv_id, role, content))
        if self.raise_on_add_message is not None:
            raise self.raise_on_add_message
        self._convs.setdefault(conv_id, {"id": conv_id, "title": "?", "messages": []})
        self._convs[conv_id]["messages"].append({"role": role, "content": content})

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._convs.values())

    def get_conversation(self, conv_id: str) -> dict[str, Any] | None:
        return self._convs.get(conv_id)

    def delete(self, conv_id: str) -> None:
        self.deleted.append(conv_id)
        self._convs.pop(conv_id, None)

    def delete_all(self) -> None:
        self.delete_all_called = True
        self._convs.clear()


class _FakeVectorFeedback:
    """Double minimal de ``VectorService`` pour ``adjust_weight``/``stats``."""

    def __init__(self, adjusted_count: int = 1) -> None:
        self.adjusted_count = adjusted_count
        self.calls: list[dict[str, Any]] = []

    def adjust_weight(self, conv_id: str, msg_id: str, delta: float, conversations: Any | None = None) -> int:
        self.calls.append({"conv_id": conv_id, "msg_id": msg_id, "delta": delta, "conversations": conversations})
        return self.adjusted_count

    def stats(self) -> dict[str, Any]:
        return {"count": 42}


@pytest.fixture
def conversations() -> _FakeConversations:
    return _FakeConversations()


@pytest.fixture
def vector_feedback() -> _FakeVectorFeedback:
    return _FakeVectorFeedback()


@pytest.fixture
def client(conversations: _FakeConversations, vector_feedback: _FakeVectorFeedback) -> TestClient:
    app = create_app()
    app.state.context = SimpleNamespace(conversations=conversations, vector=vector_feedback)
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/conversations
# ---------------------------------------------------------------------------


def test_create_conversation_titre_fourni(client: TestClient) -> None:
    resp = client.post("/api/conversations", json={"title": "Mon titre"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "Mon titre"
    assert data["conversation_id"] == "conv-1"


def test_create_conversation_sans_body_titre_par_defaut(client: TestClient) -> None:
    resp = client.post("/api/conversations")
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Nouvelle conversation"


def test_create_conversation_titre_vide_devient_titre_par_defaut(client: TestClient) -> None:
    resp = client.post("/api/conversations", json={"title": "   "})
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Nouvelle conversation"


def test_create_conversation_titre_trim(client: TestClient) -> None:
    resp = client.post("/api/conversations", json={"title": "  espaces autour  "})
    assert resp.json()["data"]["title"] == "espaces autour"


# ---------------------------------------------------------------------------
# POST /api/conversations/{conv_id}/messages
# ---------------------------------------------------------------------------


def test_add_message_nominal(client: TestClient, conversations: _FakeConversations) -> None:
    resp = client.post("/api/conversations/conv-1/messages", json={"role": "user", "content": "salut"})
    assert resp.status_code == 200
    assert resp.json()["data"] == {"status": "ok"}
    assert conversations.add_message_calls == [("conv-1", "user", "salut")]


def test_add_message_conv_id_vide_apres_strip_400(client: TestClient) -> None:
    resp = client.post("/api/conversations/%20%20/messages", json={"role": "user", "content": "x"})
    assert resp.status_code == 400
    assert "invalide" in resp.json()["error"]


def test_add_message_exception_devient_500(client: TestClient, conversations: _FakeConversations) -> None:
    conversations.raise_on_add_message = RuntimeError("disque plein")
    resp = client.post("/api/conversations/conv-1/messages", json={"role": "user", "content": "x"})
    assert resp.status_code == 500
    assert "erreur interne" in resp.json()["error"].lower()


def test_add_message_defaults_role_et_content(client: TestClient, conversations: _FakeConversations) -> None:
    resp = client.post("/api/conversations/conv-1/messages", json={})
    assert resp.status_code == 200
    assert conversations.add_message_calls == [("conv-1", "user", "")]


# ---------------------------------------------------------------------------
# GET /api/conversations
# ---------------------------------------------------------------------------


def test_list_conversations_vide(client: TestClient) -> None:
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data == {"conversations": [], "total": 0, "limit": 20, "offset": 0}


def test_list_conversations_pagination_nominale(client: TestClient, conversations: _FakeConversations) -> None:
    for i in range(5):
        conversations.create(title=f"conv {i}")
    resp = client.get("/api/conversations", params={"limit": 2, "offset": 1})
    data = resp.json()["data"]
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["conversations"]) == 2


def test_list_conversations_limit_plafonne_a_100(client: TestClient) -> None:
    resp = client.get("/api/conversations", params={"limit": 5000})
    assert resp.json()["data"]["limit"] == 100


def test_list_conversations_limit_negative_devient_zero(client: TestClient) -> None:
    resp = client.get("/api/conversations", params={"limit": -10})
    assert resp.json()["data"]["limit"] == 0


def test_list_conversations_offset_negatif_devient_zero(client: TestClient) -> None:
    resp = client.get("/api/conversations", params={"offset": -5})
    assert resp.json()["data"]["offset"] == 0


# ---------------------------------------------------------------------------
# GET /api/conversations/{conv_id}
# ---------------------------------------------------------------------------


def test_get_conversation_nominal(client: TestClient, conversations: _FakeConversations) -> None:
    conv_id = conversations.create(title="ma conv")
    resp = client.get(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "ma conv"


def test_get_conversation_introuvable_404(client: TestClient) -> None:
    resp = client.get("/api/conversations/inconnue")
    assert resp.status_code == 404
    assert "introuvable" in resp.json()["error"].lower()


def test_get_conversation_id_vide_400(client: TestClient) -> None:
    resp = client.get("/api/conversations/%20")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/conversations/{conv_id}
# ---------------------------------------------------------------------------


def test_delete_conversation_nominal(client: TestClient, conversations: _FakeConversations) -> None:
    conv_id = conversations.create()
    resp = client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"status": "ok"}
    assert conversations.deleted == [conv_id]


def test_delete_conversation_id_vide_400(client: TestClient) -> None:
    resp = client.delete("/api/conversations/%20")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/conversations (delete_all)
# ---------------------------------------------------------------------------


def test_delete_all_conversations(client: TestClient, conversations: _FakeConversations) -> None:
    resp = client.delete("/api/conversations")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"status": "ok"}
    assert conversations.delete_all_called is True


# ---------------------------------------------------------------------------
# POST /api/feedback (explicite)
# ---------------------------------------------------------------------------


def test_post_feedback_signal_positif(client: TestClient, vector_feedback: _FakeVectorFeedback) -> None:
    resp = client.post("/api/feedback", json={"conv_id": "c1", "msg_id": "m1", "signal": 1})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ok"
    assert data["adjusted"] == 1
    assert data["count"] == 42
    assert vector_feedback.calls[0]["delta"] == 1.0


def test_post_feedback_signal_negatif(client: TestClient, vector_feedback: _FakeVectorFeedback) -> None:
    resp = client.post("/api/feedback", json={"conv_id": "c1", "msg_id": "m1", "signal": -1})
    assert resp.status_code == 200
    assert vector_feedback.calls[0]["delta"] == -1.0


def test_post_feedback_signal_zero_400(client: TestClient, vector_feedback: _FakeVectorFeedback) -> None:
    resp = client.post("/api/feedback", json={"conv_id": "c1", "msg_id": "m1", "signal": 0})
    assert resp.status_code == 400
    assert "signal" in resp.json()["error"].lower()
    assert vector_feedback.calls == []


def test_post_feedback_conv_id_vide_400(client: TestClient) -> None:
    resp = client.post("/api/feedback", json={"conv_id": "  ", "msg_id": "m1", "signal": 1})
    assert resp.status_code == 400


def test_post_feedback_msg_id_vide_400(client: TestClient) -> None:
    resp = client.post("/api/feedback", json={"conv_id": "c1", "msg_id": "  ", "signal": 1})
    assert resp.status_code == 400


def test_post_feedback_signal_positif_superieur_a_un(client: TestClient, vector_feedback: _FakeVectorFeedback) -> None:
    """``signal > 0`` (pas juste ``== 1``) -> delta +1.0."""
    resp = client.post("/api/feedback", json={"conv_id": "c1", "msg_id": "m1", "signal": 5})
    assert resp.status_code == 200
    assert vector_feedback.calls[0]["delta"] == 1.0


# ---------------------------------------------------------------------------
# POST /api/feedback/implicit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "feedback_type,expected_delta",
    [
        ("copy", 0.3),
        ("edit", 0.5),
        ("revisit", 0.05),
        ("regenerate", -0.3),
        ("delete_conv", -1.0),
    ],
)
def test_post_feedback_implicit_types_connus(
    client: TestClient, vector_feedback: _FakeVectorFeedback, feedback_type: str, expected_delta: float
) -> None:
    resp = client.post(
        "/api/feedback/implicit",
        json={"conv_id": "c1", "msg_id": "m1", "type": feedback_type},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["type"] == feedback_type
    assert data["delta"] == expected_delta
    assert data["adjusted"] == 1
    assert data["count"] == 42
    assert vector_feedback.calls[0]["delta"] == expected_delta


def test_post_feedback_implicit_type_inconnu_400(client: TestClient, vector_feedback: _FakeVectorFeedback) -> None:
    resp = client.post(
        "/api/feedback/implicit",
        json={"conv_id": "c1", "msg_id": "m1", "type": "type_bidon"},
    )
    assert resp.status_code == 400
    assert "type_bidon" in resp.json()["error"]
    assert vector_feedback.calls == []


def test_post_feedback_implicit_conv_id_vide_400(client: TestClient) -> None:
    resp = client.post(
        "/api/feedback/implicit",
        json={"conv_id": "  ", "msg_id": "m1", "type": "copy"},
    )
    assert resp.status_code == 400


def test_post_feedback_implicit_msg_id_vide_400(client: TestClient) -> None:
    resp = client.post(
        "/api/feedback/implicit",
        json={"conv_id": "c1", "msg_id": "  ", "type": "copy"},
    )
    assert resp.status_code == 400
