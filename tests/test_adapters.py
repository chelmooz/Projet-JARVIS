"""Tests Adapters — OllamaAdapter, AdapterRegistry."""
import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from unittest.mock import MagicMock

from services.adapters import AdapterRegistry
from services.adapters.ollama_adapter import OllamaAdapter

# ─── OllamaAdapter ────────────────────────────────────────────────────────────

class TestOllamaAdapter:

    def test_query_returns_string(self):
        adapter = OllamaAdapter(base_url="http://localhost:99998")
        adapter._http = MagicMock()
        adapter._http.post.return_value.json.return_value = {"response": "hello!"}
        result = adapter.query("bonjour", "phi4-mini:3.8b")
        assert result == "hello!"

    def test_query_with_system(self):
        adapter = OllamaAdapter(base_url="http://localhost:99998")
        adapter._http = MagicMock()
        adapter._http.post.return_value.json.return_value = {"response": "ok"}
        result = adapter.query("test", "phi4-mini:3.8b", system="sois bref")
        assert result == "ok"

    def test_chat_returns_result(self):
        adapter = OllamaAdapter(base_url="http://localhost:99998")
        adapter._http = MagicMock()
        adapter._http.post.return_value.json.return_value = {
            "message": {"content": "chat ok"}
        }
        result = adapter.chat("phi4-mini:3.8b", [{"role": "user", "content": "hi"}])
        assert result.data.get("content") == "chat ok"

    def test_is_available_false_when_offline(self, monkeypatch):
        adapter = OllamaAdapter(base_url="http://localhost:99998")
        monkeypatch.setattr(adapter, "_fetch_models", lambda: [])
        assert adapter.is_available("phi4-mini:3.8b") is False

    def test_first_available_none_when_offline(self, monkeypatch):
        adapter = OllamaAdapter(base_url="http://localhost:99998")
        monkeypatch.setattr(adapter, "_fetch_models_raw", lambda: [])
        assert adapter.first_available() is None

    def test_first_available_skips_embedding_only_model(self, monkeypatch):
        """Reproduction du bug réel : /api/tags renvoie le modèle embedding
        en premier (dernier pulled) -> first_available() ne doit JAMAIS le
        proposer pour /api/generate (400 Bad Request garanti côté Ollama)."""
        adapter = OllamaAdapter(base_url="http://x")
        monkeypatch.setattr(adapter, "_fetch_models_raw", lambda: [
            {"name": "hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M", "capabilities": ["embedding"]},
            {"name": "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M", "capabilities": ["completion", "tools"]},
        ])
        assert adapter.first_available() == "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"

    def test_first_available_none_when_only_embedding_models(self, monkeypatch):
        adapter = OllamaAdapter(base_url="http://x")
        monkeypatch.setattr(adapter, "_fetch_models_raw", lambda: [
            {"name": "embed-only", "capabilities": ["embedding"]},
        ])
        assert adapter.first_available() is None

    def test_first_available_treats_missing_capabilities_as_available(self, monkeypatch):
        """Backward compat : anciennes versions d'Ollama sans champ 'capabilities'."""
        adapter = OllamaAdapter(base_url="http://x")
        monkeypatch.setattr(adapter, "_fetch_models_raw", lambda: [{"name": "old-model"}])
        assert adapter.first_available() == "old-model"

    def test_get_active_backend(self):
        adapter = OllamaAdapter(base_url="http://localhost:11436")
        assert "ollama" in adapter.get_active_backend()


    def test_query_payload_has_keep_alive(self):
        adapter = OllamaAdapter(base_url="http://localhost:99998")
        adapter._http = MagicMock()
        adapter._http.post.return_value.json.return_value = {"response": "ok"}
        adapter.query("test", "phi4-mini:3.8b")
        call_kwargs = adapter._http.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload.get("keep_alive") == -1

    def test_chat_payload_has_keep_alive(self):
        adapter = OllamaAdapter(base_url="http://localhost:99998")
        adapter._http = MagicMock()
        adapter._http.post.return_value.json.return_value = {"message": {"content": "ok"}}
        adapter.chat("phi4-mini:3.8b", [{"role": "user", "content": "hi"}])
        call_kwargs = adapter._http.post.call_args
        payload = call_kwargs[1]["json"]
        assert payload.get("keep_alive") == -1

    def test_close_releases_http_client(self):
        """Ex audit Qwen 3.8 : close() doit fermer et liberer le client httpx."""
        a = OllamaAdapter(base_url="http://x")
        fake = MagicMock()
        a._http = fake
        a.close()
        fake.close.assert_called_once()
        assert a._http is None

    def test_fetch_models_cached_within_ttl(self):
        """Ex audit Qwen 3.8 : _fetch_models() met en cache dans le TTL."""
        a = OllamaAdapter(base_url="http://x")

        class _Resp:
            def json(self):
                return {"models": [{"name": "m1"}]}

        fake = MagicMock()
        fake.get.return_value = _Resp()
        a._http = fake
        assert a._fetch_models() == ["m1"]
        assert a._fetch_models() == ["m1"]  # hit cache
        assert fake.get.call_count == 1


# ─── AdapterRegistry ──────────────────────────────────────────────────────────

class TestAdapterRegistry:

    def test_get_returns_ollama_adapter(self):
        reg = AdapterRegistry()
        adapter = reg.get()
        assert isinstance(adapter, OllamaAdapter)

    def test_get_returns_same_instance(self):
        reg = AdapterRegistry()
        a1 = reg.get()
        a2 = reg.get()
        assert a1 is a2

    def test_get_unknown_returns_ollama_adapter(self):
        reg = AdapterRegistry()
        adapter = reg.get("unknown")
        assert isinstance(adapter, OllamaAdapter)

    def test_get_ignores_name_param(self):
        reg = AdapterRegistry()
        a1 = reg.get("ollama")
        a2 = reg.get(None)
        a3 = reg.get("anything")
        assert a1 is a2 is a3
