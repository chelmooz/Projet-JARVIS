"""Tests AUDIT-P3.4 — Wrapper de réponse JSON standard {data, error}.

Vérifie le helper controllers/responses et la migration progressive
des endpoints GET /api/agents et GET /api/metrics (succès enveloppé).
"""
import json
import os
import sys
from unittest.mock import MagicMock

# Met la racine du projet dans sys.path (comme conftest)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from controllers import context as ctx  # noqa: E402
from controllers.responses import fail, ok  # noqa: E402


class FakeInference:
    def get_active_backend(self):
        return "ollama"

    def select_backend(self, name):
        if name != "ollama":
            raise ValueError(f"Backend inconnu : {name}")


class FakeMetrics:
    def get_metrics(self):
        return {"requests": 0, "uptime_seconds": 0}


def _setup_context():
    """Configure _ctx avec des fakes pour les tests."""
    ctx._ctx._initialized = True
    ctx._ctx.inference = FakeInference()
    ctx._ctx.memory = MagicMock()
    ctx._ctx.memory.is_healthy.return_value = True
    ctx._ctx.vector = MagicMock()
    ctx._ctx.vector.is_healthy.return_value = True
    ctx._ctx.vector.stats.return_value = {}
    ctx._ctx.conversations = MagicMock()
    ctx._ctx.agents = {k: MagicMock() for k in ("cyber", "dev", "network", "hardware", "vision")}
    ctx._ctx.log = MagicMock()
    ctx._ctx.analytics = MagicMock()
    ctx._ctx.router_svc = MagicMock()
    ctx._ctx.orchestrator = MagicMock()
    ctx._ctx.orchestrator.handle_request.return_value = {"response": "ok"}
    ctx._ctx.metrics = FakeMetrics()


_setup_context()


class TestResponseWrapperHelper:
    """Tests unitaires du helper (sans app FastAPI)."""

    def test_ok_shape(self):
        """ok() retourne {data: ..., error: null}."""
        assert ok({"a": 1}) == {"data": {"a": 1}, "error": None}

    def test_ok_default_none(self):
        assert ok() == {"data": None, "error": None}

    def test_fail_shape(self):
        """fail() retourne un JSONResponse {data: null, error: msg}."""
        resp = fail("boom", status_code=418)
        assert resp.status_code == 418
        assert json.loads(resp.body) == {"data": None, "error": "boom"}


class TestResponseWrapperEndpoints:
    """Au moins 2 endpoints réels utilisent le wrapper {data, error}."""

    def setup_method(self):
        from fastapi.testclient import TestClient

        from controllers.router import app

        _setup_context()
        self.client = TestClient(app)

    def test_agents_uses_wrapper(self):
        """GET /api/agents → {data: ..., error: null}."""
        resp = self.client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"data", "error"}
        assert data["error"] is None
        assert "profiles" in data["data"]

    def test_metrics_uses_wrapper(self):
        """GET /api/metrics → {data: ..., error: null}."""
        resp = self.client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"data", "error"}
        assert data["error"] is None
        assert isinstance(data["data"], dict)
