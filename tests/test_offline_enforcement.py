"""Tests for offline mode enforcement (P5 Ch4 / F5).

Verifies that POST /api/jarvis is blocked server-side when offline=true.
"""
import pytest
from fastapi.testclient import TestClient

from services.selector import read_preferences


def _get_client():
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Reset prefs file + cache pour éviter les pollutions inter-tests
    from config.paths import PREFERENCES_FILE
    from services.file_utils import write_json_atomic
    write_json_atomic(PREFERENCES_FILE, {"offline": False})
    from services.selector import _prefs_cache
    _prefs_cache._mtime = 0.0
    _prefs_cache._cache.clear()

    class FakeInference:
        def is_available(self, model): return True
        def resolve_model(self, model): return model
        def query(self, prompt, model, **kw): return {"response": "ok", "model": model}
        def query_multimodal(self, model, task, image): return {"response": "vision ok", "model": model}
        def embed(self, texts): return [[0.0]*384 for _ in texts]
        def list_models(self): return ["qwen2.5:latest"]
        def first_available(self): return "qwen2.5:latest"
        def select_backend(self, name): return None
        def get_active_backend(self): return "ollama"

    from unittest.mock import MagicMock
    import controllers.context as ctx_mod
    ctx_mod._ctx.inference = FakeInference()
    ctx_mod._ctx.orchestrator = MagicMock()
    ctx_mod._ctx.orchestrator.run.return_value = {
        "response": "ok", "agent": "dev", "model": "qwen2.5:latest"
    }
    ctx_mod._ctx.analytics = MagicMock()
    ctx_mod._ctx.analytics.track_query = MagicMock()
    from controllers.router import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Ch4.2 — test offline enforcement
# ---------------------------------------------------------------------------

class TestOfflineEnforcement:
    """Ch4.2 — offline setting must be enforced server-side."""

    def _reset_offline(self, client):
        client.put('/api/settings', json={'key': 'offline', 'value': False})

    def test_online_allows_request(self):
        """When offline=false, POST /api/jarvis should proceed normally."""
        client = _get_client()
        self._reset_offline(client)
        resp = client.post('/api/jarvis', json={'task': 'dis bonjour'})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("backend") != "offline"

    def test_offline_blocks_request(self):
        """When offline=true, POST /api/jarvis must return offline response."""
        client = _get_client()
        client.put('/api/settings', json={'key': 'offline', 'value': True})
        resp = client.post('/api/jarvis', json={'task': 'dis bonjour'})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("backend") == "offline", f"Expected offline, got {data.get('backend')}"
        assert "offline" in data.get("response", "").lower() or "hors-ligne" in data.get("response", "").lower()
        self._reset_offline(client)

    def test_offline_persists_across_calls(self):
        """Once set, offline mode should persist until explicitly disabled."""
        client = _get_client()
        client.put('/api/settings', json={'key': 'offline', 'value': True})
        from config.paths import PREFERENCES_FILE
        import json
        with open(PREFERENCES_FILE, encoding="utf-8") as f:
            prefs = json.load(f)
        assert prefs.get("offline") is True
        self._reset_offline(client)


# ---------------------------------------------------------------------------
# Ch4.1 — simulateNetworkCondition detection (monkey-engine.js)
# ---------------------------------------------------------------------------

class TestMonkeyEngine:
    """Ch4.1 — monkey-engine.js must have simulateNetworkCondition."""

    MONKEY_PATH = r"J:\Projet JARVIS\static\monkey-engine.js"

    def test_simulate_network_condition_exists(self):
        """simulateNetworkCondition function must be defined in monkey-engine.js."""
        import os
        if not os.path.exists(self.MONKEY_PATH):
            pytest.skip("monkey-engine.js not found")
        with open(self.MONKEY_PATH, encoding="utf-8") as f:
            content = f.read()
        assert "simulateNetworkCondition" in content, "Fonction manquante"
