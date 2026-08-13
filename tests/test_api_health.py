"""Lot 3.1 — Endpoints de santé (API) en TDD.

Objectif : valider que l'API répond en mode dégradé (sans Ollama) sans
planter, et reflète l'état réel des dépendances injectées (DI).

Contrat :
- GET /api/status -> 200, enveloppe {data:{...}, error:null}
- GET /api/health -> reflète l'état (200 si tout sain, 503 si dégradé)
"""

from __future__ import annotations

from types import SimpleNamespace

from conftest import FakeInference
from fastapi.testclient import TestClient

from controllers.router import create_app


class _PingInference:
    """InferencePort factice avec ping + is_healthy contrôlables (pour DI)."""

    def __init__(self, ping: bool, healthy: bool) -> None:
        self._ping = ping
        self._healthy = healthy

    def ping(self) -> bool:
        return self._ping

    def is_healthy(self) -> bool:
        return self._healthy


class _Healthy:
    def is_healthy(self) -> bool:
        return True


class _Unhealthy:
    def is_healthy(self) -> bool:
        return False


def _make_client(*, inference: object, healthy_services: bool) -> TestClient:
    """Construit l'app avec un contexte FAKE injecté (DI via app.state.context)."""
    app = create_app()
    svc = _Healthy() if healthy_services else _Unhealthy()
    app.state.context = SimpleNamespace(
        inference=inference,
        vector=svc,
        memory=svc,
        conversations=svc,
    )
    return TestClient(app)


def test_status_200_offline_degraded() -> None:
    # FakeInference n'expose ni ping ni is_healthy -> tout dégradé, mais 200.
    client = _make_client(inference=FakeInference(), healthy_services=False)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    data = body["data"]
    assert data["ollama"] is False
    assert "version" in data


def test_status_reflects_injected_backend() -> None:
    client = _make_client(inference=_PingInference(ping=True, healthy=True), healthy_services=True)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ollama"] is True
    assert data["inference"] is True
    assert data["vector"] is True


def test_health_degraded_returns_503() -> None:
    client = _make_client(inference=_PingInference(ping=False, healthy=False), healthy_services=False)
    resp = client.get("/api/health")
    assert resp.status_code == 503
    assert resp.json()["healthy"] is False


def test_health_all_healthy_returns_200() -> None:
    client = _make_client(inference=_PingInference(ping=True, healthy=True), healthy_services=True)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["healthy"] is True
