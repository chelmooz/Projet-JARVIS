"""Tests des routes conversations — prouve le bug d'import précoce (singletons figés à None).

LE RED / GREEN / REFACTOR est :
- RED : sans le fix, conversations et metrics sont None → 500
- GREEN : avec get_context() à l'exécution → 200

Ce module est immunisé contre la pollution d'état par test_api.py
(qui sauvegarde le contexte avant build_app() et le restore à None).
"""
import pytest
from fastapi.testclient import TestClient

from controllers.di import AppContext
from controllers.router import app

app.state.context = AppContext()
app.state.context.initialize()
client = TestClient(app)


def _data(resp):
    return resp.json()["data"]


def test_list_conversations_returns_200_not_500():
    response = client.get("/api/conversations")
    assert response.status_code == 200
    body = _data(response)
    assert "conversations" in body


def test_create_then_get_conversation_roundtrip():
    create_resp = client.post("/api/conversations", json={"title": "test_e2e"})
    assert create_resp.status_code == 200
    data = _data(create_resp)
    assert "conversation_id" in data
    conv_id = data["conversation_id"]

    get_resp = client.get(f"/api/conversations/{conv_id}")
    assert get_resp.status_code == 200
    assert _data(get_resp)["id"] == conv_id


def test_get_metrics_returns_200_not_500():
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert "requests" in response.json()["data"]


class TestConversationsPagination:
    """AUDIT-P1.1 — pagination limit/offset sur GET /api/conversations."""

    @staticmethod
    def _seed(n: int):
        client.delete("/api/conversations")
        for i in range(n):
            client.post("/api/conversations", json={"title": f"pagination_{i}"})

    def test_pagination_limit_offset(self):
        self._seed(3)
        resp = client.get("/api/conversations?limit=2&offset=0")
        assert resp.status_code == 200
        data = _data(resp)
        assert len(data["conversations"]) <= 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_limit_zero_returns_empty(self):
        self._seed(3)
        resp = client.get("/api/conversations?limit=0")
        assert resp.status_code == 200
        data = _data(resp)
        assert data["conversations"] == []
        assert data["total"] == 3

    def test_offset_beyond_total_returns_empty(self):
        self._seed(3)
        resp = client.get("/api/conversations?offset=100")
        assert resp.status_code == 200
        data = _data(resp)
        assert data["conversations"] == []
        assert data["total"] == 3

    def test_limit_clamped_to_max_100(self):
        self._seed(3)
        resp = client.get("/api/conversations?limit=500")
        assert resp.status_code == 200
        data = _data(resp)
        assert data["limit"] <= 100
