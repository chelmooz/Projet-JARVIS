"""Fixtures et doubles de test partagés pour la suite JARVIS.

Permet de tester services/contrôleurs sans Ollama, réseau ni disque hors tmp_path.
Les fakes des ports (InferencePort/VectorPort/...) sont ajoutés par lot (1.2, 1.3).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from models import Result
from ports import ChatPort, EmbeddingPort, VectorPort


@pytest.fixture(autouse=True)
def _isolate_environ() -> Iterator[None]:
    """Snapshot/restore ``os.environ`` autour de chaque test (Lot 0.2).

    Empêche qu'un test qui mute ``os.environ`` (directement ou via un module
    important une variable au chargement) ne pollue les tests suivants dans
    la même session pytest. Filet de sécurité en complément de ``monkeypatch``,
    qui ne couvre pas les mutations faites au niveau module (import-time).
    """
    before = dict(os.environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(before)


@pytest.fixture
def sandbox_root(tmp_path: Path) -> Iterator[Path]:
    """Positionne ``JARVIS_FILES_SANDBOX_ROOT`` sur ``tmp_path`` et restaure après le test.

    Le sandbox de ``services/file_system.py`` est *fail-closed* : sans cette variable
    il lève ``FileSystemError``. La fixture fournit donc une racine valide et isolée.
    """
    previous = os.environ.get("JARVIS_FILES_SANDBOX_ROOT")
    os.environ["JARVIS_FILES_SANDBOX_ROOT"] = str(tmp_path)
    try:
        yield tmp_path
    finally:
        if previous is None:
            os.environ.pop("JARVIS_FILES_SANDBOX_ROOT", None)
        else:
            os.environ["JARVIS_FILES_SANDBOX_ROOT"] = previous


class FakeInference(ChatPort):
    """``ChatPort`` déterministe : renvoie une réponse configurable (echo par défaut)."""

    def __init__(self, response: str = "fake-answer") -> None:
        self.response = response
        self.last_prompt: str | None = None
        self.last_model: str | None = None
        self.last_messages: list[dict[str, Any]] | None = None

    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        self.last_prompt = prompt
        self.last_model = model
        return self.response

    def chat(self, model: str, messages: list[dict[str, Any]]) -> Result:
        self.last_model = model
        self.last_messages = messages
        return Result.ok(data={"text": self.response}, agent="fake", model=model)


fake_inference: ChatPort = FakeInference()


@pytest.fixture
def inference() -> ChatPort:
    """Fournit le ``ChatPort`` factice déterministe."""
    return fake_inference


class FakeEmbedding(EmbeddingPort):
    """``EmbeddingPort`` en mémoire : vecteur constant déterministe (dérivé du texte)."""

    def __init__(self, dim: int = 8) -> None:
        self.dim = dim

    def embed(self, text: str, model: str | None = None) -> list[float]:
        return [float((len(text) % (i + 1)) + 1) for i in range(self.dim)]


class FakeVector(VectorPort):
    """``VectorPort`` en mémoire : index/recherche triviale (pas de similarité réelle)."""

    def __init__(self) -> None:
        self._docs: list[tuple[str, dict[str, Any] | None]] = []

    def index(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        self._docs.append((text, metadata))

    def index_batch(self, documents: list[tuple[str, dict[str, Any] | None]]) -> None:
        self._docs.extend(documents)

    def vectorize_pending(self) -> int:
        return len(self._docs)

    def search(
        self,
        query: str,
        top_k: int = 5,
        agent: str | None = None,
        sim_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        docs = [
            (text, metadata) for text, metadata in self._docs if agent is None or (metadata or {}).get("agent") == agent
        ]
        return [{"text": text, "metadata": metadata, "score": 1.0} for text, metadata in docs[:top_k]]

    def stats(self) -> dict[str, Any]:
        return {"count": len(self._docs)}

    def preload(self) -> None:
        return None

    def is_healthy(self) -> bool:
        return True


fake_embedding: EmbeddingPort = FakeEmbedding()
fake_vector: VectorPort = FakeVector()


@pytest.fixture
def embedding() -> EmbeddingPort:
    """Fournit le ``EmbeddingPort`` factice."""
    return fake_embedding


@pytest.fixture
def vector() -> VectorPort:
    """Fournit le ``VectorPort`` factice."""
    return fake_vector
