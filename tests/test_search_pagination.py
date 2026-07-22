"""Tests de pagination pour GET /api/search (AUDIT-P1.1).

On remplace le VectorService réel par un faux déterministe renvoyant une
liste fixe de résultats, afin de valider la troncature limit/offset et le
champ `total` sans dépendre d'Ollama ni du disque.
"""
import pytest
from fastapi.testclient import TestClient

import controllers.context as ctx_mod
from controllers.router import app

app.state.context = ctx_mod._ctx
client = TestClient(app)


class _FakeVector:
    """VectorService factice : renvoie toujours la liste complète de résultats."""

    def __init__(self, results):
        self._results = results

    def search(self, query, top_k: int = 5):
        # Le faux ignore top_k et renvoie tout, pour tester la troncature en Python
        if not query:
            return []
        return self._results

    def stats(self):
        return {}


@pytest.fixture(autouse=True)
def _fake_vector():
    # Cinq résultats factices déterministes
    results = [
        {"text": f"doc {i}", "metadata": {"source": "test"}, "score": round(1.0 - i * 0.1, 4)}
        for i in range(5)
    ]
    original = ctx_mod._ctx.vector
    ctx_mod._ctx.vector = _FakeVector(results)
    yield
    ctx_mod._ctx.vector = original


class TestSearchPagination:
    """AUDIT-P1.1 — pagination limit/offset sur GET /api/search."""

    def test_pagination_limit_offset(self):
        # limit=2 doit renvoyer <= 2 items + champ total
        resp = client.get("/api/search?q=test&limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["results"]) <= 2
        assert data["total"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_limit_zero_returns_empty(self):
        # limit=0 doit renvoyer une liste vide (pas d'erreur)
        resp = client.get("/api/search?q=test&limit=0")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["results"] == []
        assert data["total"] == 5

    def test_offset_beyond_total_returns_empty(self):
        # offset > total doit renvoyer une liste vide
        resp = client.get("/api/search?q=test&offset=100")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["results"] == []
        assert data["total"] == 5

    def test_limit_clamped_to_max_100(self):
        # La limite doit être plafonnée à 100 côté serveur
        resp = client.get("/api/search?q=test&limit=500")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["limit"] <= 100

    def test_default_total_present(self):
        # Le champ total doit toujours être présent par défaut
        resp = client.get("/api/search?q=test")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "total" in data
        assert data["total"] == 5
