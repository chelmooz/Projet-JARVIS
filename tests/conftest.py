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
from ports import ChatPort


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
