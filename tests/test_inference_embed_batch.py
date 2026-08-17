"""Tests RED→GREEN pour InferenceService.embed_batch (délégation DIP).

Contexte MT-KB-L2i : avant ce commit, ``services/vector.py:268`` appelait
``self._inference.embed_batch(texts)`` mais ``InferenceService`` (``services/inference.py:70-72``)
ne déléguait que ``embed()`` — ``embed_batch`` ABSENTE. Conséquence (MT-KB-L2h) :
l'ingestion Phase 2 a produit 904 docs avec embeddings null, search = 0 résultat.

Couvre :
1. ``test_embed_batch_delegates_to_adapter`` : délégation effective + transmission (texts, model=None).
2. ``test_embed_batch_model_optionnel`` : ``embed_batch(texts)`` et ``embed_batch(texts, model="x")``
   passent sans erreur (signature alignée sur ``LLMAdapter.embed_batch``).
"""

from __future__ import annotations

import pytest

from services.inference import InferenceService

# ---------------------------------------------------------------------------
# Double de la frontière externe : le LLMAdapter (port ``services/adapters/protocols.py:88``).
# ---------------------------------------------------------------------------


class _FakeLLMAdapter:
    """Fake du LLMAdapter : enregistre les appels embed_batch et retourne des vecteurs contrôlés."""

    def __init__(self, batch_vectors: list[list[float]] | None = None) -> None:
        self.batch_vectors = batch_vectors if batch_vectors is not None else [[0.1, 0.2]]
        self.embed_batch_calls: list[tuple[list[str], str | None]] = []

    def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        self.embed_batch_calls.append((list(texts), model))
        return [list(v) for v in self.batch_vectors]


# ---------------------------------------------------------------------------
# Test 1 : InferenceService.embed_batch délègue à LLMAdapter.embed_batch
# ---------------------------------------------------------------------------


def test_embed_batch_delegates_to_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """embed_batch(["a","b"]) retourne les vecteurs du fake et transmet (texts, model=None)."""
    expected_vectors = [[0.1, 0.2], [0.3, 0.4]]
    fake = _FakeLLMAdapter(batch_vectors=expected_vectors)

    inference = InferenceService()
    monkeypatch.setattr(inference, "_adapter", lambda: fake)

    result = inference.embed_batch(["a", "b"])
    assert result == expected_vectors
    assert fake.embed_batch_calls == [(["a", "b"], None)], f"Attendu [([a,b], None)], reçu {fake.embed_batch_calls}"


# ---------------------------------------------------------------------------
# Test 2 : embed_batch(texts) et embed_batch(texts, model="x") passent sans erreur
# ---------------------------------------------------------------------------


def test_embed_batch_model_optionnel(monkeypatch: pytest.MonkeyPatch) -> None:
    """embed_batch accepte model=None (défaut) et model explicite sans erreur."""
    fake = _FakeLLMAdapter(batch_vectors=[[0.0]])
    inference = InferenceService()
    monkeypatch.setattr(inference, "_adapter", lambda: fake)

    # Sans model → model=None transmis
    inference.embed_batch(["x"])
    # Avec model explicite → transmis tel quel
    inference.embed_batch(["y"], model="custom-embedding-model")

    assert fake.embed_batch_calls == [(["x"], None), (["y"], "custom-embedding-model")], (
        f"Appels attendus: [([x], None), ([y], custom-embedding-model)], reçu {fake.embed_batch_calls}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
