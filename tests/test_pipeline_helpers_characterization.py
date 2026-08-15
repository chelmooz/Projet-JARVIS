from __future__ import annotations

from services.pipeline_helpers import build_failure, build_hyde_query, has_fatal_error, is_stagnant


def test_is_stagnant_requires_non_initial_attempt_and_same_reason() -> None:
    assert is_stagnant("same", "same", 1) is True
    assert is_stagnant("same", "same", 0) is False
    assert is_stagnant("new", "same", 1) is False


def test_build_hyde_query_contains_task_response_and_instruction() -> None:
    query = build_hyde_query("task", "previous")
    assert "task" in query
    assert "previous" in query
    assert "Affine" in query


def test_has_fatal_error_handles_empty_success_and_failure() -> None:
    assert has_fatal_error([]) is False
    assert has_fatal_error([{"error": None}]) is False
    assert has_fatal_error([{"error": "boom"}]) is True


def test_build_failure_uses_last_error_and_default() -> None:
    failure = build_failure("p", [{"error": "boom"}])
    assert failure["pipeline"] == "p"
    assert failure["steps"] == 1
    assert failure["error"] == "boom"
    assert build_failure("p", [{}])["error"] == "Erreur inconnue"
