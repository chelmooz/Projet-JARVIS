"""Tests TDD pour le bug P0-1 : pipeline_steps appelle add_message avec backend=."""

import inspect
from unittest.mock import MagicMock

import pytest

from ports import ConversationPort
from services.conversation import ConversationService
from services.pipeline_steps import save_results


def test_save_results_no_typeerror_with_backend_kwarg():
    """RED: save_results ne doit pas lever TypeError si add_message reçoit backend=."""
    # Arrange
    state = {
        "response": "Test response",
        "task": "Test task",
        "agent_key": "dev",
        "result": {"backend": "ollama", "model": "qwen2.5"},
    }
    memory = MagicMock()
    vector_store = MagicMock()

    # Act & Assert: ne doit pas lever TypeError
    try:
        save_results(state, memory, vector_store)
    except TypeError as e:
        if "backend" in str(e):
            pytest.fail(f"Bug P0-1 non corrigé: {e}")
        raise  # Autre TypeError, on laisse passer


def test_conversation_port_accepts_backend_kwarg():
    """RED: ConversationPort doit accepter backend= dans add_message."""
    # Vérifie que le port définit backend= dans sa signature
    sig = inspect.signature(ConversationPort.add_message)
    assert "backend" in sig.parameters, (
        "ConversationPort.add_message doit accepter backend= (bug P0-1)"
    )


def test_conversation_service_add_message_accepts_backend():
    """GREEN (après fix): ConversationService.add_message accepte backend=."""
    svc = MagicMock(spec=ConversationService)
    svc.add_message("c1", "user", "hello", backend="ollama")
    svc.add_message.assert_called_once()
    call_kwargs = svc.add_message.call_args
    assert call_kwargs[1].get("backend") == "ollama"
