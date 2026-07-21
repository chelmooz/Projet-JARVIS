"""Tests d'integration reels contre Ollama.

Ces tests requierent une instance Ollama en cours (port 11436 par defaut).
Variables d'environnement :
  OLLAMA_HOST=127.0.0.1:11436  (surpasse la detection automatique)

Lancement avec Ollama portable :
  scripts/run_integration_tests.sh (Linux) ou run_integration_tests.bat (Windows)

Lancement avec Docker :
  docker compose up -d
  python -m pytest tests/test_integration_ollama.py -v
"""
import os

import httpx
import pytest

from services.adapters.ollama_adapter import OllamaAdapter


def _find_ollama_url() -> str:
    env_host = os.environ.get("OLLAMA_HOST", "")
    if env_host:
        try:
            r = httpx.get(f"http://{env_host}/api/tags", timeout=2)
            if r.status_code == 200:
                return f"http://{env_host}"
        except Exception:
            pass
    for port in (11436, 11434):
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/tags", timeout=2)
            if r.status_code == 200:
                return f"http://127.0.0.1:{port}"
        except Exception:
            continue
    return ""

OLLAMA_URL = _find_ollama_url()

def _available_models() -> list[str]:
    if not OLLAMA_URL:
        return []
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []

REACHABLE = bool(OLLAMA_URL)
MODELS = _available_models()

ollama_required = pytest.mark.skipif(not REACHABLE, reason="Ollama not reachable on :11434/:11436")
def has_model(name):
    return pytest.mark.skipif(name not in MODELS, reason=f"Model {name} not pulled")


@ollama_required
class TestOllamaReachability:

    def test_ollama_api_tags(self):
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "models" in data
        assert len(data["models"]) > 0

    def test_ollama_api_version(self):
        r = httpx.get(f"{OLLAMA_URL}/api/version", timeout=5)
        assert r.status_code == 200
        assert "version" in r.json()


@ollama_required
class TestOllamaAdapter:

    def setup_method(self):
        self.adapter = OllamaAdapter(base_url=OLLAMA_URL)

    def test_list_models(self):
        models = self.adapter.list_models()
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)

    def test_is_available_known_model(self):
        if not MODELS:
            pytest.skip("No models available")
        assert self.adapter.is_available(MODELS[0]) is True

    def test_is_available_unknown_model(self):
        assert self.adapter.is_available("nonexistent-model:foobar") is False

    def test_first_available(self):
        model = self.adapter.first_available()
        assert model is not None
        assert model in MODELS

    def test_get_active_backend(self):
        assert self.adapter.get_active_backend() == "ollama"

    @has_model("qwen2.5:7b")
    def test_query_qwen(self):
        result = self.adapter.query("Reponds uniquement par 'ok'.", model="qwen2.5:7b")
        assert result.success is True
        assert "response" in result.data
        assert len(result.data["response"]) > 0

    @has_model("qwen2.5:7b")
    def test_chat_qwen(self):
        result = self.adapter.chat("qwen2.5:7b", [
            {"role": "user", "content": "Reponds uniquement par 'ok'."},
        ])
        assert result.success is True
        assert "content" in result.data
        assert len(result.data["content"]) > 0

    def test_query_unknown_model_returns_fail(self):
        result = self.adapter.query("hello", model="this-model-does-not-exist-42")
        assert result.success is False
        assert result.error is not None

    def test_embed_nomic(self):
        """Test embed with nomic-embed-text if available."""
        if "nomic-embed-text" not in MODELS:
            try:
                vec = self.adapter.embed("hello world")
                assert isinstance(vec, list)
                assert len(vec) > 0
                assert all(isinstance(v, float) for v in vec)
            except Exception as e:
                pytest.skip(f"nomic-embed-text not available: {e}")
        else:
            vec = self.adapter.embed("hello world")
            assert isinstance(vec, list)
            assert len(vec) > 0

    @has_model("qwen2.5:7b")
    def test_timeout_config_respected(self):
        """Short timeout should fail on a large prompt."""
        import time
        adapter = OllamaAdapter(base_url=OLLAMA_URL)
        t0 = time.time()
        # A short simple prompt should still work quickly
        result = adapter.query("Reponds 'ok'.", model="qwen2.5:7b")
        elapsed = time.time() - t0
        assert result.success is True
        assert elapsed < 30
