"""Tests TDD — Embeddings vectoriels (OllamaAdapter + VectorService)."""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np

from services.adapters.ollama_adapter import OllamaAdapter
from services.vector import EXPECTED_DIM, EXPECTED_MODEL, VectorService


class TestOllamaAdapterEmbed:

    def test_embed_returns_768d(self):
        adapter = OllamaAdapter(base_url="http://127.0.0.1:11436")
        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1] * 768]}
        mock_response.raise_for_status = lambda: None
        with patch.object(adapter._http, "post", return_value=mock_response):
            vec = adapter.embed("hello world")
        assert len(vec) == 768
        assert all(isinstance(v, float) for v in vec)

    def test_embed_default_model(self):
        adapter = OllamaAdapter(base_url="http://127.0.0.1:11436")
        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.5] * 768]}
        mock_response.raise_for_status = lambda: None
        with patch.object(adapter._http, "post") as mock_post:
            mock_post.return_value = mock_response
            adapter.embed("test")
            _, kwargs = mock_post.call_args
            assert kwargs["json"]["model"] == "nomic-embed-text-v2-moe"
            assert kwargs["json"]["input"] == ["test"]

    def test_embed_custom_model(self):
        adapter = OllamaAdapter(base_url="http://127.0.0.1:11436")
        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.5] * 768]}
        mock_response.raise_for_status = lambda: None
        with patch.object(adapter._http, "post") as mock_post:
            mock_post.return_value = mock_response
            adapter.embed("test", model="phi4-mini:3.8b")
            _, kwargs = mock_post.call_args
            assert kwargs["json"]["model"] == "phi4-mini:3.8b"


class TestCosineSimilarityThreshold:

    def test_close_vectors_above_08(self):
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_b = np.array([0.95, 0.05, 0.0], dtype=np.float32)
        sim = float(np.dot(vec_a, vec_b))
        assert sim > 0.8

    def test_far_vectors_below_03(self):
        vec_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec_c = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        norm = np.linalg.norm(vec_c)
        vec_c_norm = vec_c / norm
        sim = float(np.dot(vec_a, vec_c_norm))
        assert sim < 0.3

    def test_identical_vectors_score_1(self):
        vec = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        sim = float(np.dot(vec, vec))
        assert abs(sim - 1.0) < 1e-6


class TestVectorDimensionMigration:

    def test_stale_dimension_invalidates_on_init(self):
        old_data = {
            "documents": [{"text": "ancien", "metadata": {}, "embedding": [0.1] * 16}],
            "embeddings": [[0.1] * 16],
            "embedding_dim": 16,
            "embedding_model": "fallback_histogram",
        }
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(old_data, f)
                temp_path = f.name
            with patch("services.vector.VECTOR_PATH", temp_path):
                v = VectorService()
                # Migration : les textes sont preserves (re-index paresseux) mais les
                # embeddings existants sont invalides et la dimension/modele mis a jour.
                assert len(v._data["documents"]) == 1
                assert v._data["documents"][0]["embedding"] is None
                assert v._data["embedding_dim"] == EXPECTED_DIM
                assert v._data["embedding_model"] == EXPECTED_MODEL
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_matching_dimension_keeps_data(self):
        good_data = {
            "documents": [{"text": "conserve", "metadata": {}, "embedding": [0.1] * EXPECTED_DIM}],
            "embedding_dim": EXPECTED_DIM,
            "embedding_model": EXPECTED_MODEL,
        }
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(good_data, f)
                temp_path = f.name
            with patch("services.vector.VECTOR_PATH", temp_path):
                v = VectorService()
                assert len(v._data["documents"]) == 1
                assert v._data["documents"][0]["text"] == "conserve"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_stats_includes_embedding_fields(self):
        v = VectorService()
        stats = v.stats()
        assert "embedding_backend" in stats
        assert "embedding_model" in stats
        assert "embedding_dim" in stats
        assert "using_fallback" in stats
        assert stats["embedding_model"] == EXPECTED_MODEL
        assert stats["embedding_dim"] == EXPECTED_DIM
