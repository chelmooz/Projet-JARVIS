from typing import Any

from ports import ChatPort


def test_fake_inference_query(inference: ChatPort) -> None:
    response = inference.query("bonjour", "model-x")
    assert response == "fake-answer"
    assert inference.last_prompt == "bonjour"
    assert inference.last_model == "model-x"


def test_fake_inference_chat_returns_result(inference: ChatPort) -> None:
    messages: list[dict[str, Any]] = [{"role": "user", "content": "bonjour"}]
    result = inference.chat("model-x", messages)
    assert result.success
    assert result.data == {"text": "fake-answer"}
    assert inference.last_messages == messages
