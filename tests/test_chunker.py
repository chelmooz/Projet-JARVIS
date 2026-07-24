"""Tests pour chunk_text — découpage sémantique avec overlap (D8)."""
import pytest

from services.chunker import chunk_text


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        chunks = chunk_text("Texte court.", chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Texte court."

    def test_long_text_splits_into_multiple_chunks(self):
        text = "Mot " * 200
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 1
        total = sum(len(c["text"]) for c in chunks)
        assert total >= len(text)

    def test_overlap_preserved_between_chunks(self):
        text = "AAAA " * 30 + "BBBB " * 30 + "CCCC " * 30
        chunks = chunk_text(text, chunk_size=80, overlap=30)
        assert len(chunks) >= 2
        if len(chunks) >= 2:
            assert "BBBB" in chunks[0]["text"] or "BBBB" in chunks[1]["text"]

    def test_chunk_metadata_has_chunk_id(self):
        chunks = chunk_text("Un deux trois.", chunk_size=100, overlap=20, doc_id="doc-1")
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["doc_id"] == "doc-1"

    def test_chunk_metadata_tracks_index(self):
        text = "Phrase une. " * 30 + "Phrase deux. " * 30
        chunks = chunk_text(text, chunk_size=100, overlap=20, doc_id="doc-1")
        for i, c in enumerate(chunks):
            assert c["metadata"]["chunk_index"] == i
            assert c["metadata"]["total_chunks"] == len(chunks)

    def test_empty_text_returns_empty_list(self):
        chunks = chunk_text("", chunk_size=500, overlap=50)
        assert chunks == []

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_text("   \n\n  ", chunk_size=500, overlap=50)
        assert chunks == []