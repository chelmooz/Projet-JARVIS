"""Tests MT 7.3 — Juge isolé (Verifier Sub-Agent).

Vérifie que LlmResponseJudge :
- évalue une réponse sans voir le raisonnement de l'acteur (SKILL.md §6)
- retourne un dict structuré {"score": float, "reason": str}
- lève une exception si le JSON est invalide
"""

from unittest.mock import MagicMock

import pytest

from services.adapters.protocols import LLMAdapter
from services.rag_judge import LlmResponseJudge


@pytest.fixture
def mock_llm_adapter():
    """Mock de LLMAdapter pour isoler le test."""
    adapter = MagicMock(spec=LLMAdapter)
    return adapter


@pytest.fixture
def judge(mock_llm_adapter):
    """Instance de LlmResponseJudge avec le mock injecté."""
    return LlmResponseJudge(llm_adapter=mock_llm_adapter)


def test_judge_returns_structured_score(judge, mock_llm_adapter):
    """RED→GREEN : Le juge retourne un dict structuré avec score et reason."""
    # ARRANGE
    query = "Problème réseau sur le switch A"
    chunks = ["Le switch A a un port défectueux", "Vérifier le câble Ethernet"]
    response = "Remplacer le câble Ethernet du port 3 du switch A."

    # Le LLM retourne un JSON valide
    mock_llm_adapter.query.return_value = {
        "response": '{"score": 0.85, "reason": "La réponse est pertinente et actionnable."}'
    }

    # ACT
    result = judge.evaluate(query, chunks, response)

    # ASSERT
    assert isinstance(result, dict)
    assert "score" in result
    assert "reason" in result
    assert isinstance(result["score"], float)
    assert isinstance(result["reason"], str)
    assert 0.0 <= result["score"] <= 1.0
    assert result["score"] == 0.85


def test_judge_does_not_see_actor_reasoning(judge, mock_llm_adapter):
    """SKILL.md §6 : Le juge ne voit PAS le raisonnement de l'acteur."""
    # ARRANGE
    query = "Problème réseau"
    chunks = ["Chunk 1", "Chunk 2"]
    response = "Réponse finale"

    mock_llm_adapter.query.return_value = {
        "response": '{"score": 0.7, "reason": "OK"}'
    }

    # ACT
    judge.evaluate(query, chunks, response)

    # ASSERT — Vérifier que le prompt envoyé au LLM ne contient
