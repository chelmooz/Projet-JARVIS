"""Lot 3.2 — POST /api/jarvis : routage agent + nominal + validation (TDD, sans Ollama).

On injecte (DI via ``app.state.context``) des doubles :
- un orchestrateur factice délégant le routage au *vrai* ``AgentRouter`` ;
- un orchestrateur factice produisant une réponse via ``FakeInference`` (nominal) ;
On valide aussi la validation de payload (422) et la limite de taille de body (413).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeInference
from fastapi.testclient import TestClient

from controllers.router import create_app
from services.router import AgentRouter


class _RoutingOrchestrator:
    """Orchestrateur factice : délègue le routage au vrai AgentRouter."""

    def __init__(self, router: AgentRouter) -> None:
        self._router = router

    async def handle_request(self, task: str, image: str | None = None, conv_id: str | None = None) -> dict:
        agent = self._router.select_agent(task)
        return {"response": f"routed:{agent}", "agent": agent, "model": "fake"}


class _InferenceOrchestrator:
    """Orchestrateur factice : routage + réponse produite par FakeInference."""

    def __init__(self, router: AgentRouter, inference: FakeInference) -> None:
        self._router = router
        self._inference = inference

    async def handle_request(self, task: str, image: str | None = None, conv_id: str | None = None) -> dict:
        agent = self._router.select_agent(task)
        reply = self._inference.query(task, model="fake", system=None)
        return {"response": reply, "agent": agent, "model": "fake"}


class _Analytics:
    def track_query(self, **_: object) -> None:
        return None


class _Conversations:
    def add_message(self, *args: object, **kwargs: object) -> None:
        return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Évite toute lecture de préférences disque (offline) pendant le test.
    monkeypatch.setattr("controllers.routes.jarvis.read_preferences", lambda: {})
    app = create_app()
    app.state.context = SimpleNamespace(
        orchestrator=_RoutingOrchestrator(AgentRouter()),
        analytics=_Analytics(),
        conversations=_Conversations(),
        inference=None,
    )
    return TestClient(app)


@pytest.fixture
def client_inference(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("controllers.routes.jarvis.read_preferences", lambda: {})
    inference = FakeInference(response="fake reply")
    app = create_app()
    app.state.context = SimpleNamespace(
        orchestrator=_InferenceOrchestrator(AgentRouter(), inference),
        analytics=_Analytics(),
        conversations=_Conversations(),
        inference=inference,
    )
    return TestClient(app)


def test_route_by_prefix_cyber(client: TestClient) -> None:
    resp = client.post("/api/jarvis", json={"task": "@cyber audit the firewall logs"})
    assert resp.status_code == 200
    assert resp.json()["agent"] == "cyber"


def test_route_by_keyword_network(client: TestClient) -> None:
    resp = client.post("/api/jarvis", json={"task": "diagnostiquer la connectivite reseau et le dns"})
    assert resp.status_code == 200
    assert resp.json()["agent"] == "network"


def test_route_fallback_dev(client: TestClient) -> None:
    resp = client.post("/api/jarvis", json={"task": "bonjour, comment ca va ?"})
    assert resp.status_code == 200
    assert resp.json()["agent"] == "dev"


def test_route_by_prefix_dev(client: TestClient) -> None:
    resp = client.post("/api/jarvis", json={"task": "@dev ecris un script python"})
    assert resp.status_code == 200
    assert resp.json()["agent"] == "dev"


def test_nominal_with_fake_inference(client_inference: TestClient) -> None:
    resp = client_inference.post("/api/jarvis", json={"task": "@dev ecrire une fonction"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "fake reply"
    assert body["agent"] == "dev"


def test_invalid_payload_422(client: TestClient) -> None:
    # `task` est requis -> FastAPI répond 422 (Validation Error).
    resp = client.post("/api/jarvis", json={"not_task": "hello"})
    assert resp.status_code == 422


def test_body_too_large_413(monkeypatch: pytest.MonkeyPatch) -> None:
    # Réduit la limite pour rendre le test déterministe et léger.
    monkeypatch.setattr("controllers.middlewares.MAX_BODY_SIZE", 10)
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/jarvis", json={"task": "x" * 100})
    assert resp.status_code == 413
    assert resp.json()["error"] == "Payload too large"
