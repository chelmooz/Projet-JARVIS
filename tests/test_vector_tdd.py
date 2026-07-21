"""Tests TDD refactor VectorService — facade fine delegate aux modules SRP.

Le contrat public est preserve ; on verifie que VectorService orchestre sans
tout refaire lui-meme (delegation aux modules vector_index/embedder/dimension/
weighting).
"""
from services import vector as vector_mod
from services.vector import VectorService


class TestVectorServiceFacade:

    def test_index_delegates_to_vector_index(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(tmp_path / "vector_index.json"))
        from controllers import context as ctx_mod
        monkeypatch.setattr(ctx_mod._ctx, "inference", None)

        v = VectorService()
        v.index("hello world", {"source": "test"})
        # dedup géré par le module VectorIndex
        v.index("hello world", {"source": "test"})
        assert len(v._data["documents"]) == 1

    def test_search_uses_cache_then_embed_then_rank(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(tmp_path / "vector_index.json"))
        from controllers import context as ctx_mod
        monkeypatch.setattr(ctx_mod._ctx, "inference", None)

        v = VectorService()
        v.index("hello world", {"source": "test"})
        v.vectorize_pending()
        # 1er appel = miss, 2e = hit (cache delegue a VectorCache)
        v.search("hello", top_k=1)
        v.search("hello", top_k=1)
        s = v.stats()
        assert s["cache_hits"] == 1
        assert s["cache_misses"] == 1

    def test_embedder_fallback_when_no_backend(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(tmp_path / "vector_index.json"))
        from controllers import context as ctx_mod
        monkeypatch.setattr(ctx_mod._ctx, "inference", None)

        v = VectorService()
        v.index("texte", {"src": "x"})
        v.vectorize_pending()
        assert v._embedder.using_fallback is True
        assert s["embedding_backend"] == "fallback_histogram" if (s := v.stats()) else True

    def test_weighting_delegates_consolidate(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(tmp_path / "vector_index.json"))
        from controllers import context as ctx_mod
        monkeypatch.setattr(ctx_mod._ctx, "inference", None)

        v = VectorService()
        v.index_message("c1", "m1", "user", "hello", 1.0)
        v.index_message("c1", "m2", "user", "hello", 1.0)
        v.vectorize_pending()
        assert len(v._data["documents"]) == 2
        v.consolidate()
        # les 2 docs identiques sont deduples par WeightConsolidator
        assert len(v._data["documents"]) == 1
        assert v.stats()["consolidation_runs"] == 1

    def test_dimension_migration_on_init(self, tmp_path, monkeypatch):
        index = tmp_path / "vector_index.json"
        monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(index))
        from controllers import context as ctx_mod
        monkeypatch.setattr(ctx_mod._ctx, "inference", None)

        v1 = VectorService()
        v1.index("texte conserve", {"src": "mig"})
        v1.vectorize_pending()
        assert v1.last_migration == "ok"

        # changement de dimension attendue -> reindex au prochain init
        monkeypatch.setattr(vector_mod, "EXPECTED_DIM", 512)
        monkeypatch.setattr(
            VectorService, "_resolve_expected_dim",
            lambda self: 512,
        )
        v2 = VectorService()
        assert v2.last_migration in ("reindexed", "reset")
        assert "texte conserve" in [d["text"] for d in v2._data["documents"]]
