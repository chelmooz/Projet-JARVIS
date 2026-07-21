"""Tests TDD extraction vector.py en modules SRP (façon analysis_*.py).

Chaque responsabilite devient un module independant ; VectorService reste une
façade fine qui delegate. Le contrat public + l'acces a v._data sont preserves
(tests existants y accedent).
"""
from services import vector as vector_mod


class TestVectorDimensionExtraction:

    def test_dimension_manager_detects_mismatch(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(index))
        from services.vector_dimension import DimensionManager
        data = {"documents": [{"text": "a", "embedding": None}], "embedding_dim": 768,
                "embedding_model": "nomic-embed-text-v2-moe"}
        mgr = DimensionManager(data)
        status = mgr.ensure_dimension(expected_dim=512, expected_model="nomic-embed-text-v2-moe")
        assert status in ("reindexed", "reset")

    def test_dimension_manager_reindex_keeps_text(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(index))
        from services.vector_dimension import DimensionManager
        data = {"documents": [{"text": "keep", "embedding": [0.0] * 768}],
                "embedding_dim": 768, "embedding_model": "nomic-embed-text-v2-moe"}
        mgr = DimensionManager(data)
        status = mgr._schedule_reindex(data["documents"], 512, "nomic-embed-text-v2-moe", 1)
        assert status == "reindexed"
        assert data["documents"][0]["embedding"] is None
        assert data["documents"][0]["text"] == "keep"


class TestVectorEmbedderExtraction:

    def test_embedder_fallback_histogram(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(index))
        from services.vector_embedder import Embedder
        emb = Embedder(inference=None)
        out = emb.embed("texte de test pour le repli")
        assert len(out) == 16
        assert abs(sum(out) - 1.0) < 1e-6
        assert emb.using_fallback is True


class TestVectorWeightingExtraction:

    def test_weight_consolidator_dedup_keeps_max(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(index))
        from config.constants import CONSOLIDATE_DEDUP_SIMILARITY, CONSOLIDATE_MAX_ITER
        from services.vector_weighting import WeightConsolidator
        docs = [
            {"text": "dup", "metadata": {"weight": 1.0, "source": "x", "created_at": 1.0}, "embedding": [1.0, 0.0]},
            {"text": "dup", "metadata": {"weight": 3.0, "source": "x", "created_at": 1.0}, "embedding": [1.0, 0.0]},
        ]
        wc = WeightConsolidator(docs)
        to_remove = wc.dedup(CONSOLIDATE_DEDUP_SIMILARITY, CONSOLIDATE_MAX_ITER)
        assert 1 in to_remove
        assert docs[0]["metadata"]["weight"] == 3.0  # max conserve


class TestVectorIndexExtraction:

    def test_index_add_document_dedup(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(index))
        from services.vector_index import VectorIndex
        data = {"documents": [], "embedding_dim": 768, "embedding_model": "nomic"}
        idx = VectorIndex(data)
        assert idx.add_document("texte", {}) is True
        assert idx.add_document("texte", {}) is False
        assert len(data["documents"]) == 1
