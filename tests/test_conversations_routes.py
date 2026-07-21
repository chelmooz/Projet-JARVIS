"""Tests des routes conversations — prouve le bug d'import précoce (singletons figés à None).

LE RED / GREEN / REFACTOR est :
- RED : sans le fix, conversations et metrics sont None → 500
- GREEN : avec get_context() à l'exécution → 200

Ce module est immunisé contre la pollution d'état par test_api.py
(qui sauvegarde le contexte avant build_app() et le restore à None).
"""
import pytest
from fastapi.testclient import TestClient

import controllers.context as ctx
from controllers.router import app


@pytest.fixture(autouse=True, scope="module")
def _ensure_context():
    """Réinitialise le contexte AVANT les tests (pas à l'import),
    pour être immunisé contre la pollution de test_api.py qui
    sauvegarde/restaure l'état global à None."""
    if not ctx._ctx.ready or ctx._ctx.conversations is None:
        from controllers.context import build_app
        build_app()
    yield


client = TestClient(app)


def test_list_conversations_returns_200_not_500():
    response = client.get("/api/conversations")
    assert response.status_code == 200
    body = response.json()
    assert "conversations" in body


def test_create_then_get_conversation_roundtrip():
    create_resp = client.post("/api/conversations", json={"title": "test_e2e"})
    assert create_resp.status_code == 200
    data = create_resp.json()
    assert "conversation_id" in data
    conv_id = data["conversation_id"]

    get_resp = client.get(f"/api/conversations/{conv_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == conv_id


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
        # Vérifie que limit/offset tronque la liste et expose le total
        self._seed(3)
        resp = client.get("/api/conversations?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["conversations"]) <= 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_limit_zero_returns_empty(self):
        # limit=0 doit renvoyer une liste vide (pas d'erreur)
        self._seed(3)
        resp = client.get("/api/conversations?limit=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversations"] == []
        assert data["total"] == 3

    def test_offset_beyond_total_returns_empty(self):
        # offset > total doit renvoyer une liste vide
        self._seed(3)
        resp = client.get("/api/conversations?offset=100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversations"] == []
        assert data["total"] == 3

    def test_limit_clamped_to_max_100(self):
        # La limite doit être plafonnée à 100 côté serveur
        self._seed(3)
        resp = client.get("/api/conversations?limit=500")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] <= 100
