from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.rag_judge import JudgeParseError, LlmResponseJudge


class Adapter:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def query(self, prompt, model):
        self.calls.append((prompt, model))
        return self.raw


def test_format_chunks_and_prompt_isolated() -> None:
    judge = LlmResponseJudge(Adapter("{}"), model="model")
    assert judge._format_chunks([]) == "(aucun document fourni)"
    assert judge._format_chunks(["one", "two"]) == "- [1] one\n- [2] two"
    prompt = judge._build_prompt("query", ["doc"], "response")
    assert "query" in prompt and "doc" in prompt and "response" in prompt
    assert "raisonnement" not in prompt.lower()


def test_extract_text_supports_object_dict_and_raw() -> None:
    judge = LlmResponseJudge(Adapter("{}"))
    assert judge._extract_text(SimpleNamespace(data={"response": "object"})) == "object"
    assert judge._extract_text({"response": "dict"}) == "dict"
    assert judge._extract_text("raw") == "raw"


def test_evaluate_calls_adapter_and_normalizes_score() -> None:
    adapter = Adapter('{"score": 1.5, "reason": "good"}')
    result = LlmResponseJudge(adapter, model="m").evaluate("q", ["doc"], "answer")
    assert result == {"score": 1.0, "reason": "good"}
    assert adapter.calls[0][1] == "m"


def test_evaluate_supports_markdown_fence_and_low_clamp() -> None:
    judge = LlmResponseJudge(Adapter('```json\n{"score": -1, "reason": 2}\n```'))
    assert judge.evaluate("q", [], "a") == {"score": 0.0, "reason": "2"}


@pytest.mark.parametrize(
    "raw, message",
    [
        ("not json", "JSON invalide"),
        ("[]", "attendu dict"),
        ('{"reason": "x"}', "score.*manquant"),
        ('{"score": 0.5}', "reason.*manquant"),
        ('{"score": "bad", "reason": "x"}', "doit être numérique"),
    ],
)
def test_invalid_judge_outputs_raise(raw: str, message: str) -> None:
    with pytest.raises(JudgeParseError, match=message):
        LlmResponseJudge(Adapter(raw)).evaluate("q", [], "a")
