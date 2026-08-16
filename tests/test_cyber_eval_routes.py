"""MT-Lot12-L8 — Route API ``POST /api/cyber/analyze``.

Le service ``CyberEvalService`` est mocké via le singleton module (zéro appel
Ollama réel). Validation Pydantic du body testée nativement (422).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app
from controllers.routes import cyber_eval as cyber_eval_routes


class FakeCyberEvalService:
    """Double du service : réponse déterministe, enregistre les appels."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def analyze(self, question: str, max_revisions: int = 2) -> dict[str, Any]:
        self.calls.append((question, max_revisions))
        return {"decision": "publish", "score": 0.85, "reasoning": "OK", "revisions": 0}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App avec le service mocké (singleton module remplacé)."""
    monkeypatch.setattr(cyber_eval_routes, "_service", FakeCyberEvalService())
    return TestClient(create_app())


def test_analyze_endpoint_returns_service_result(client: TestClient) -> None:
    """POST valide → 200 + dict identique à celui du service."""
    resp = client.post("/api/cyber/analyze", json={"question": "test"})
    assert resp.status_code == 200
    assert resp.json() == {"decision": "publish", "score": 0.85, "reasoning": "OK", "revisions": 0}


def test_analyze_endpoint_passes_max_revisions(client: TestClient) -> None:
    """``max_revisions`` du body transmis au service."""
    resp = client.post("/api/cyber/analyze", json={"question": "test", "max_revisions": 1})
    assert resp.status_code == 200
    fake = cyber_eval_routes._service
    assert fake is not None
    assert fake.calls == [("test", 1)]


def test_analyze_endpoint_default_max_revisions(client: TestClient) -> None:
    """Sans ``max_revisions`` → défaut 2."""
    resp = client.post("/api/cyber/analyze", json={"question": "test"})
    assert resp.status_code == 200
    fake = cyber_eval_routes._service
    assert fake is not None
    assert fake.calls == [("test", 2)]


def test_analyze_endpoint_rejects_empty_question(client: TestClient) -> None:
    """Question vide → 422 (validation Pydantic)."""
    resp = client.post("/api/cyber/analyze", json={"question": ""})
    assert resp.status_code == 422


def test_analyze_endpoint_rejects_missing_question(client: TestClient) -> None:
    """Question absente → 422 (validation Pydantic)."""
    resp = client.post("/api/cyber/analyze", json={})
    assert resp.status_code == 422
