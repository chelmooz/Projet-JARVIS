"""Tests MT-KB-L2x — Filtrage par agent et seuil de similarité (retrieval).

Utilise le vrai ``VectorService`` (chemin de recherche complet) avec un
``FakeInferenceService`` contrôlé (vecteurs L2-normalisés déterministes) et
``VECTOR_PATH`` monkeypatché sur ``tmp_path`` (aucun I/O hors tmp_path).
"""

from __future__ import annotations

import pytest

import services.vector as vector_module
from services.vector import VectorService
from services.vector_search import cosine_search


class FakeInferenceService:
    """Double du service d'inférence : embeddings contrôlés par texte."""

    def __init__(self, embeddings: dict[str, list[float]]) -> None:
        self.embeddings = embeddings

    def embed(self, text: str) -> list[float]:
        return list(self.embeddings[text])

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [list(self.embeddings[t]) for t in texts]


def _make_service(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory, inference: FakeInferenceService
) -> VectorService:
    """Construit un VectorService isolé sur tmp_path (VECTOR_PATH monkeypatché)."""
    vpath = tmp_path / "vector_index.json"
    monkeypatch.setattr(vector_module, "VECTOR_PATH", str(vpath))
    return VectorService(inference)


def test_search_filters_by_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """Une recherche avec ``agent="@cyber"`` ne retourne que les docs @cyber."""
    svc = _make_service(
        monkeypatch,
        tmp_path,
        FakeInferenceService(
            {
                "cyber doc": [0.95, 0.312, 0.0, 0.0],
                "dev doc": [0.7, 0.714, 0.0, 0.0],
                "query": [1.0, 0.0, 0.0, 0.0],
            }
        ),
    )
    svc.index("cyber doc", {"agent": "@cyber"})
    svc.index("dev doc", {"agent": "@dev"})
    svc.vectorize_pending()

    results = svc.search("query", top_k=5, agent="@cyber")

    assert len(results) == 1
    assert results[0]["metadata"]["agent"] == "@cyber"


def test_search_applies_sim_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """Le seuil par défaut 0.5 filtre les résultats < 0.5 ; 0.0 les garde."""
    svc = _make_service(
        monkeypatch,
        tmp_path,
        FakeInferenceService(
            {
                "far doc": [0.3, 0.954, 0.0, 0.0],
                "query": [1.0, 0.0, 0.0, 0.0],
            }
        ),
    )
    svc.index("far doc", {"agent": "@dev"})
    svc.vectorize_pending()

    assert svc.search("query", top_k=5) == []
    assert len(svc.search("query", top_k=5, sim_threshold=0.0)) == 1


def test_cosine_search_threshold_param() -> None:
    """``cosine_search`` accepte ``sim_threshold`` et filtre avant le ranking."""
    docs = [
        {"text": "close", "embedding": [0.95, 0.312], "metadata": {}},
        {"text": "far", "embedding": [0.3, 0.954], "metadata": {}},
    ]
    assert len(cosine_search([1.0, 0.0], docs, top_k=5)) == 1
    assert len(cosine_search([1.0, 0.0], docs, top_k=5, sim_threshold=0.0)) == 2
