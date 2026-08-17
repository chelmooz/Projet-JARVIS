"""MT-KB-L2j — Replacement isolé de ``tests/test_vector_corrupted.py``.

Le test historique ``tests/test_vector_corrupted.py`` ligne 47 détruit le VRAI
``MEMORY_DIR`` de production via ``shutil.rmtree(MEMORY_DIR, ignore_errors=True)``
à chaque exécution de pytest — l'index vectoriel Phase 2 (904 docs dans
``memory/vector_index.json``) a été perdu par force majeure.

Cette suite le remplace par 3 tests qui ne touchent JAMAIS le disque de
production : ``VECTOR_PATH`` est monkeypatché vers ``tmp_path`` (pattern
déjà éprouvé dans ``test_vector_service_characterization.py``).
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

import tests.test_vector_corrupted as _legacy_test_module
from config.paths import MEMORY_DIR
from services.vector import VectorService


class _StubInference:
    """Service d'inférence factice : embeddings constants 768-dim.

    Référence les méthodes réellement appelées par ``VectorService``
    (``embed`` warmup, ``embed_batch`` vectorisation) sans dépendance Ollama.
    """

    def embed(self, text: str) -> list[float]:
        return [0.0] * 768

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]


def _run_corrupted_index_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VectorService:
    """Scénario « index corrompu » isolé sur ``tmp_path``.

    ``VECTOR_PATH`` est redirigé vers ``tmp_path/vector_index.json`` : aucune
    écriture/renommage/suppression ne touche le vrai ``MEMORY_DIR``.
    """
    vpath = tmp_path / "vector_index.json"
    monkeypatch.setattr("services.vector.VECTOR_PATH", str(vpath))
    vpath.write_bytes(b'{"documents"')
    return VectorService(_StubInference())


def test_corrupted_index_is_recognized_without_touching_production(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = _run_corrupted_index_isolated(tmp_path, monkeypatch)
    assert svc.stats()["total"] == 0


def test_production_memory_dir_untouched_after_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = sorted(os.listdir(MEMORY_DIR))
    _run_corrupted_index_isolated(tmp_path, monkeypatch)
    after = sorted(os.listdir(MEMORY_DIR))
    assert before == after, (
        f"Le vrai MEMORY_DIR a été modifié par le test isolé — avant : {before!r} — après : {after!r}"
    )


def test_no_rmtree_on_production_path() -> None:
    source = inspect.getsource(_legacy_test_module)
    forbidden = [
        "shutil.rmtree(MEMORY_DIR",
        "shutil.rmtree(str(MEMORY_DIR)",
        "os.rmdir(MEMORY_DIR",
        "os.rmdir(str(MEMORY_DIR)",
    ]
    violations = [p for p in forbidden if p in source]
    assert not violations, (
        f"Pattern(s) destructif(s) présent(s) dans tests/test_vector_corrupted.py : "
        f"{violations!r}. Ces appels détruisent le vrai MEMORY_DIR de production."
    )
