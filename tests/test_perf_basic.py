"""Tests de performance basiques — endpoints non-bloquants < 200ms."""
import time

from fastapi.testclient import TestClient

from controllers.router import app
from services.ratelimit import _hits

client = TestClient(app)


class TestPerfEndpoints:

    def setup_method(self):
        """Vide le bucket rate-limit avant chaque test perf."""
        _hits.clear()
    def test_jarvis_info_under_200ms(self):
        start = time.perf_counter()
        resp = client.get("/api/jarvis")
        elapsed = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed < 200, f"GET /api/jarvis took {elapsed:.0f}ms"

    def test_backend_under_200ms(self):
        start = time.perf_counter()
        resp = client.get("/api/backend")
        elapsed = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed < 200, f"GET /api/backend took {elapsed:.0f}ms"

    def test_metrics_under_200ms(self):
        start = time.perf_counter()
        resp = client.get("/api/metrics")
        elapsed = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed < 200, f"GET /api/metrics took {elapsed:.0f}ms"

    def test_agents_list_under_200ms(self):
        start = time.perf_counter()
        resp = client.get("/api/agents")
        elapsed = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        assert elapsed < 200, f"GET /api/agents took {elapsed:.0f}ms"
