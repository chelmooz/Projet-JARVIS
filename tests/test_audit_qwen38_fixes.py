"""TDD — Correctifs audit Qwen 3.8 (encodage logs, fermeture httpx, cache modèles, cohérence persistence)."""
from unittest.mock import MagicMock

from services.adapters.ollama_adapter import OllamaAdapter


def test_close_releases_http_client():
    a = OllamaAdapter(base_url="http://x")
    fake = MagicMock()
    a._http = fake
    a.close()
    fake.close.assert_called_once()
    assert a._http is None


def test_fetch_models_cached_within_ttl():
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


def test_save_conv_persists_full_response_not_truncated():
    from controllers.routes.jarvis import _save_conv

    captured = {}

    class _Conv:
        def add_message(self, cid, role, content, **kw):
            captured[role] = content

    long_resp = "R" * 1500  # > 1000 (ancien plafond) et < 2000 (MAX_MESSAGE_LENGTH)
    _save_conv("c", "t", {"response": long_resp, "agent": "dev", "model": "m"}, "dev", _Conv())
    assert captured["assistant"] == long_resp  # plus de troncature a 1000
