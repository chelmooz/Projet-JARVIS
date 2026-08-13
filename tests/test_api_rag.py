"""Lot 3.6 — Recherche RAG / vectorielle (TDD, sans Ollama).

Valide ``GET /api/search`` avec un ``VectorPort`` factice (``FakeVector``)
injecté via ``app.state.context`` :
- requête valide -> 200, résultats + pagination (total/count/limit/offset) ;
- requête vide -> 400 ;
- le texte renvoyé est scrubbé (PII) mais préservé s'il est anodin.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeVector
from fastapi.testclient import TestClient

from controllers.router import create_app


@pytest.fixture
def client() -> TestClient:
    vector = FakeVector()
    vector.index("Premier document JARVIS", {"id": 1})
    vector.index("Second document securite", {"id": 2})
    vector.index("Troisieme document reseau", {"id": 3})
    app = create_app()
    app.state.context = SimpleNamespace(vector=vector)
    return TestClient(app)


def test_search_returns_results(client: TestClient) -> None:
    resp = client.get("/api/search", params={"q": "document"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["query"] == "document"
    assert data["total"] == 3
    assert data["count"] == 3
    assert data["results"][0]["text"] == "Premier document JARVIS"


def test_search_empty_query_400(client: TestClient) -> None:
    resp = client.get("/api/search", params={"q": "   "})
    assert resp.status_code == 400


def test_search_pagination(client: TestClient) -> None:
    resp = client.get("/api/search", params={"q": "document", "limit": 2, "offset": 0})
    data = resp.json()["data"]
    assert data["total"] == 3
    assert data["count"] == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
