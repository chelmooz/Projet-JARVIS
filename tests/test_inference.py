"""Tests pour InferenceService — Façade LLM (couche critique)."""
from unittest.mock import MagicMock

import pytest

from models import Result
from services.adapters.protocols import LLMAdapter
from services.inference import InferenceService


@pytest.fixture
def service():
    return InferenceService()


def _mock_adapter(service):
    """Injecte un adaptateur mock pour les tests unitaires."""
    mock = MagicMock(spec=LLMAdapter)
    service._adapter = lambda: mock
    return mock


class TestQuery:
    def test_query_returns_string(self, service):
        mock = _mock_adapter(service)
        mock.query.return_value = "response:test:hello worl"
        result = service.query("hello world", "test")
        assert isinstance(result, str)

    def test_query_with_system_prompt(self, service):
        mock = _mock_adapter(service)
        mock.query.return_value = "ok"
        result = service.query("hello", "test", system="Be concise")
        assert isinstance(result, str)
        assert mock.query.called

    def test_query_empty_prompt_returns_string(self, service):
        mock = _mock_adapter(service)
        mock.query.return_value = ""
        result = service.query("", "test")
        assert isinstance(result, str)


class TestQueryMultimodal:
    def test_multimodal_returns_dict(self, service):
        mock = _mock_adapter(service)
        mock.query_multimodal.return_value = {"description": "image ok"}
        result = service.query_multimodal("test", "describe", "img")
        assert isinstance(result, dict)
        assert "description" in result


class TestChat:
    def test_chat_returns_result(self, service):
        mock = _mock_adapter(service)
        mock.chat.return_value = Result(success=True, data={"reply": "chat ok"},
                                        agent="test", model="test")
        result = service.chat("test", [{"role": "user", "content": "hi"}])
        assert isinstance(result, Result)
        assert result.success


class TestAvailability:
    def test_is_available_true(self, service):
        mock = _mock_adapter(service)
        mock.is_available.return_value = True
        assert service.is_available("test") is True

    def test_first_available_returns_string(self, service):
        mock = _mock_adapter(service)
        mock.first_available.return_value = "test-model"
        assert service.first_available() == "test-model"

    def test_list_models_returns_list(self, service):
        mock = _mock_adapter(service)
        mock.list_models.return_value = ["test-model"]
        models = service.list_models()
        assert isinstance(models, list)


class TestBackend:
    def test_get_active_backend(self, service):
        assert service.get_active_backend() == "ollama"

class TestDefaultRegistry:
    def test_default_registry_get_active_backend(self):
        svc = InferenceService()
        assert isinstance(svc.get_active_backend(), str)


class TestClose:
    def test_close_closes_adapter(self):
        svc = InferenceService()
        fake_adapter = MagicMock()
        svc._registry = MagicMock()
        svc._registry.get.return_value = fake_adapter
        svc.close()
        fake_adapter.close.assert_called_once()
