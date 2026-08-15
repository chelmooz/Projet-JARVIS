"""Tests TDD pour controllers/router.py - E1 : create_app().

Tous les tests utilisent TestClient sans déclencher le lifespan complet
(l'assignation de ``app.state.context`` se fait directement dans ``create_app``).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from controllers.router import create_app


class TestCreateAppRoutes:
    def test_create_app_has_root_route(self) -> None:
        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200

    def test_create_app_has_status_route(self) -> None:
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.status_code == 200

    def test_create_app_has_models_route(self) -> None:
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/models")
        assert response.status_code == 200

    def test_create_app_has_metrics_route(self) -> None:
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/metrics")
        assert response.status_code == 200

    def test_create_app_has_backend_route(self) -> None:
        app = create_app()
        client = TestClient(app)
        response = client.get("/api/backend")
        assert response.status_code == 200


class TestCreateAppMiddlewares:
    def test_create_app_injects_context(self) -> None:
        app = create_app()
        assert hasattr(app.state, "context"), "app.state.context must be injected"

    def test_create_app_has_status_cache(self) -> None:
        app = create_app()
        assert hasattr(app.state, "status_cache"), "app.state.status_cache must be set"

    def test_create_app_has_status_lock(self) -> None:
        app = create_app()
        assert hasattr(app.state, "status_lock"), "app.state.status_lock must be set"


class TestCreateAppContent:
    def test_create_app_returns_fastapi(self) -> None:
        app = create_app()
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_create_app_home_returns_welcome(self) -> None:
        app = create_app()
        client = TestClient(app)
        response = client.get("/")
        text = response.text.lower()
        assert "jarvis" in text or "api" in text
