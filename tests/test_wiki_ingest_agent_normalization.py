"""Tests MT-KB-L2x — Normalisation ``@agent`` et ``chunk_id`` à l'ingest wiki.

Passe par ``WikiIngestService.ingest_phase2`` (chemin runtime réel) avec un
store vectoriel factice qui capture les metadata, racine wiki sur tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.wiki_ingest_service import WikiIngestService


class FakeInferenceService:
    """Double du service d'inférence pour l'ingest (embedding 4 dims suffit)."""

    def embed(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3, 0.4]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


class FakeVectorStore:
    """Capture les metadata des chunks ingérés (remplace VectorService)."""

    def __init__(self) -> None:
        self.batch: list[tuple[str, dict[str, Any]]] = []

    def index_batch(self, documents: list[tuple[str, dict[str, Any] | None]]) -> None:
        self.batch.extend(documents)  # type: ignore[arg-type]

    def vectorize_pending(self) -> int:
        return 0


def _entry(entry_id: str, agent: str) -> dict[str, Any]:
    return {"id": entry_id, "agent": agent, "source": "test-source", "text": f"Contenu {entry_id}", "metadata": {}}


def _make_wiki(tmp_path: Path) -> WikiIngestService:
    wiki = WikiIngestService(tmp_path / "wiki")
    (wiki.wiki_root / "sources").mkdir(parents=True, exist_ok=True)
    return wiki


def test_ingest_phase2_normalizes_agent_in_metadata(tmp_path: Path) -> None:
    """``"cyber"`` devient ``"@cyber"`` dans les metadata des chunks."""
    wiki = _make_wiki(tmp_path)
    with (wiki.wiki_root / "sources" / "test.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(_entry("X-1", "cyber")) + "\n")

    store = FakeVectorStore()
    wiki.ingest_phase2(FakeInferenceService(), files=["test.jsonl"], vector_store=store)

    assert store.batch, "aucun chunk ingéré"
    for _, metadata in store.batch:
        assert metadata["agent"] == "@cyber"


def test_ingest_phase2_keeps_prefixed_and_strips_whitespace(tmp_path: Path) -> None:
    """``"@dev"`` reste ``"@dev"`` ; ``" @hardware "`` devient ``"@hardware"``."""
    wiki = _make_wiki(tmp_path)
    with (wiki.wiki_root / "sources" / "test.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(_entry("X-2", "@dev")) + "\n")
        f.write(json.dumps(_entry("X-3", " @hardware ")) + "\n")

    store = FakeVectorStore()
    wiki.ingest_phase2(FakeInferenceService(), files=["test.jsonl"], vector_store=store)

    agents = sorted(metadata["agent"] for _, metadata in store.batch)
    assert agents == ["@dev", "@hardware"]


def test_ingest_phase2_metadata_has_chunk_id(tmp_path: Path) -> None:
    """Chaque chunk porte un ``chunk_id`` stable ``<id>:<chunk_index>`` (ADR-008)."""
    wiki = _make_wiki(tmp_path)
    with (wiki.wiki_root / "sources" / "test.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(_entry("X-4", "@cyber")) + "\n")

    store = FakeVectorStore()
    wiki.ingest_phase2(FakeInferenceService(), files=["test.jsonl"], vector_store=store)

    assert store.batch, "aucun chunk ingéré"
    for _, metadata in store.batch:
        assert metadata["chunk_id"] == f"X-4:{metadata['chunk_index']}"
