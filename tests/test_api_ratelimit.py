"""Lot 3.5 — Rate limiting API (TDD, sans Ollama).

Valide le contrat du middleware de quota (``controllers.middlewares`` /
``services.ratelimit``) :
- sous le quota : 200 + en-têtes ``X-RateLimit-Limit`` / ``X-RateLimit-Remaining`` ;
- au-delà : 429 + corps ``retry_after`` cohérent avec l'en-tête ``Retry-After``.

``MAX_REQUESTS`` est abaissé (patch) et l'état du limiter réinitialisé pour
un test déterministe et léger (aucun appel réseau).
"""

from __future__ import annotations

from collections import defaultdict

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app
from services import ratelimit


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(ratelimit, "MAX_REQUESTS", 2)
    monkeypatch.setattr("controllers.middlewares.MAX_REQUESTS", 2)
    monkeypatch.setattr(ratelimit, "_hits", defaultdict(list))
    app = create_app()
    return TestClient(app)


def test_headers_within_limit(client: TestClient) -> None:
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.headers["X-RateLimit-Limit"] == "2"
    assert resp.headers["X-RateLimit-Remaining"] == "1"


def test_429_after_limit_with_coherent_retry_after(client: TestClient) -> None:
    # MAX_REQUESTS=2 -> les 2 premières passent, la 3e est bloquée.
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/status").status_code == 200
    resp = client.get("/api/status")
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"] == "Too many requests"
    assert "retry_after" in body
    # Cohérence corps <-> en-tête (audit : retry_after dérivé de la fenêtre réelle).
    assert resp.headers["Retry-After"] == str(body["retry_after"])


def test_429_retry_after_derived_from_ratelimit_window(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Lot 5.1 : retry_after dérivé de services.ratelimit.WINDOW (source unique
    # de vérité), plus de 60 codé en dur. WINDOW patché à 3 -> 429 avec 3.
    monkeypatch.setattr(ratelimit, "WINDOW", 3)
    monkeypatch.setattr("controllers.middlewares.WINDOW", 3)
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/status").status_code == 200
    resp = client.get("/api/status")
    assert resp.status_code == 429
    assert resp.json()["retry_after"] == 3
    assert resp.headers["Retry-After"] == "3"
