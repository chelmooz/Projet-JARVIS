"""Tests VectorService — Embedding cache et recherche."""
import pytest

from controllers import context as ctx_mod
from services import vector as vector_mod
from services.vector import VectorService
from services.vector_search import cosine_search


import numpy as _np


class _FakeInference:
    def embed(self, text):
        emb = [0.0] * 768
        for i, c in enumerate(text[:10]):
            emb[i] = ord(c) / 255.0
        norm = _np.linalg.norm(emb)
        return (emb / norm).tolist() if norm > 0 else [1.0] + [0.0] * 767


@pytest.fixture(autouse=True)
def _isolated_index(tmp_path, monkeypatch):
    """Isole l'index vectoriel sur disque et force le fallback embedding
    deterministe (ctx.inference=None) pour eviter la contamination inter-tests
    via l'etat global partage."""
    monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(tmp_path / "vector_index.json"))
    monkeypatch.setattr(ctx_mod._ctx, "inference", None)


class TestVectorService:

    def test_search_caches_same_query(self):
        v = VectorService(_FakeInference())
        v.index("hello world", {"source": "test"})
        v.vectorize_pending()
        r1 = v.search("hello", top_k=1)
        r2 = v.search("hello", top_k=1)
        assert r1 == r2
        assert len(r1) == 1

    def test_search_empty_returns_empty(self):
        v = VectorService(_FakeInference())
        assert v.search("") == []

    def test_stats(self):
        v = VectorService(_FakeInference())
        stats = v.stats()
        assert "total" in stats
        assert "embedded" in stats
        assert stats["total"] >= 0
        assert "cache_hits" in stats
        assert "cache_misses" in stats
        assert "cache_hit_rate" in stats
        assert stats["cache_hit_rate"] == 0

    def test_cache_hits_tracked(self):
        v = VectorService(_FakeInference())
        v.index("bonjour le monde", {"src": "test"})
        v.vectorize_pending()
        v.search("bonjour", top_k=1)
        v.search("bonjour", top_k=1)
        stats = v.stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["cache_hit_rate"] == 50.0

    def test_cosine_search_top_k_and_order(self):
        docs = [
            {"text": "a", "metadata": {}, "embedding": [1.0, 0.0, 0.0]},
            {"text": "b", "metadata": {}, "embedding": [1.0, 1.0, 0.0]},
            {"text": "c", "metadata": {}, "embedding": [0.0, 0.0, 1.0]},
        ]
        # Requête alignée sur 'a' => 'a' en premier
        top = cosine_search([1.0, 0.0, 0.0], docs, top_k=2)
        assert len(top) == 2
        assert top[0]["text"] == "a"
        # Requête alignée sur 'b' => 'b' en premier
        top = cosine_search([1.0, 1.0, 0.0], docs, top_k=3)
        assert top[0]["text"] == "b"
        # top_k tronque
        assert len(cosine_search([1.0, 0.0, 0.0], docs, top_k=1)) == 1

    def test_cosine_search_skips_invalid_embeddings(self):
        docs = [
            {"text": "a", "metadata": {}, "embedding": None},
            {"text": "b", "metadata": {}, "embedding": [1.0, 0.0]},
            {"text": "c", "metadata": {}, "embedding": [1.0, 0.0]},
        ]
        top = cosine_search([1.0, 0.0], docs, top_k=5)
        assert [d["text"] for d in top] == ["b", "c"]


class TestIndexMessage:
    """Etape 1/2 : indexation par cle conv_id:msg_id avec provenance."""

    def test_index_message_stores_metadata(self):
        v = VectorService(_FakeInference())
        v.index_message("conv1", "msg1", "user", "bonjour", 1000.0)
        docs = v._data["documents"]
        assert len(docs) == 1
        meta = docs[0]["metadata"]
        assert meta["source"] == "conversation"
        assert meta["conv_id"] == "conv1"
        assert meta["msg_id"] == "msg1"
        assert meta["role"] == "user"
        assert meta["weight"] == 1.0
        assert meta["created_at"] == 1000.0

    def test_index_message_dedup_by_key(self):
        v = VectorService(_FakeInference())
        v.index_message("conv1", "msg1", "user", "hello", 1.0)
        v.index_message("conv1", "msg1", "user", "hello", 2.0)  # meme cle -> pas de doublon
        assert len(v._data["documents"]) == 1

    def test_index_message_empty_content_skipped(self):
        v = VectorService(_FakeInference())
        v.index_message("conv1", "msg1", "user", "   ", 1.0)
        assert len(v._data["documents"]) == 0

    def test_ingest_message_indexes_and_embeds(self):
        v = VectorService(_FakeInference())
        v.ingest_message("conv1", "msg1", "user", "bonsoir", 1.0)
        docs = v._data["documents"]
        assert len(docs) == 1
        assert docs[0]["embedding"] is not None


class TestAdjustWeight:
    """Etape 3 : ajustement du poids d'un souvenir."""

    def test_adjust_weight_updates_doc(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "test", 1.0)
        v.ingest_message("c1", "m1", "user", "test", 1.0)
        v.adjust_weight("c1", "m1", 1.5)
        doc = v._data["documents"][0]
        assert doc["metadata"]["weight"] == 2.5

    def test_adjust_weight_clamp(self):
        from config.constants import WEIGHT_MAX, WEIGHT_MIN
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "test", 1.0)
        v.ingest_message("c1", "m1", "user", "test", 1.0)
        v.adjust_weight("c1", "m1", 10.0)
        assert v._data["documents"][0]["metadata"]["weight"] == WEIGHT_MAX
        v.adjust_weight("c1", "m1", -20.0)
        assert v._data["documents"][0]["metadata"]["weight"] == WEIGHT_MIN

    def test_adjust_weight_changes_search_ranking(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m_a", "user", "bonjour le monde", 1.0)
        v.index_message("c1", "m_b", "user", "bonjour la terre", 1.0)
        v.vectorize_pending()
        v.adjust_weight("c1", "m_a", 3.0)  # m_a = 4.0, m_b = 1.0
        results = v.search("bonjour", top_k=2)
        assert results[0]["metadata"]["msg_id"] == "m_a", "poids eleve doit etre en tete"

    def test_adjust_weight_clears_cache(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "hello", 1.0)
        v.vectorize_pending()
        v.search("hello", top_k=1)
        misses_before = v.stats()["cache_misses"]
        v.adjust_weight("c1", "m1", 1.0)
        v.search("hello", top_k=1)
        misses_after = v.stats()["cache_misses"]
        assert misses_after > misses_before, "cache vide doit forcer un miss supplementaire"


class TestWeightedStats:
    """Etape 6 : observabilite poids dans stats()."""

    def test_stats_includes_weight_fields(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "hello", 1.0)
        v.index_message("c1", "m2", "user", "world", 1.0)
        stats = v.stats()
        assert "weight_mean" in stats
        assert "low_weight_ratio" in stats
        assert "conversation_docs" in stats
        assert stats["conversation_docs"] == 2
        assert stats["weight_mean"] == 1.0
        assert stats["low_weight_ratio"] == 0.0

    def test_weight_stats_after_adjust(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "hello", 1.0)
        v.index_message("c1", "m2", "user", "world", 1.0)
        v.adjust_weight("c1", "m1", -1.5)  # → -0.5
        stats = v.stats()
        assert stats["low_weight_ratio"] == 0.5  # 1/2 <= 0
        assert stats["weight_mean"] == pytest.approx(0.25, abs=0.01)  # (1.0 + -0.5)/2


class TestRecency:
    """Etape 4 : decroissance de la recence dans la recherche ponderee."""

    def test_recency_favors_recent_doc(self):
        import time
        now = time.time()
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "bonjour", now - 40 * 3600)
        v.index_message("c1", "m2", "user", "bonjour aussi", now)
        v.vectorize_pending()
        results = v.search("bonjour", top_k=2)
        assert results[0]["metadata"]["msg_id"] == "m2", (
            "le doc recent doit ranker avant l'ancien (recence > 0.5)"
        )
        # verifie que le score du vieux doc est reduit
        old_score = next(r["score"] for r in results if r["metadata"]["msg_id"] == "m1")
        assert old_score < results[0]["score"], "vieux score < score recent"

    def test_top_k_5_default(self):
        v = VectorService(_FakeInference())
        for i in range(8):
            v.index_message("c1", f"m{i}", "user", f"doc {i} similaire", 1.0)
        v.vectorize_pending()
        results = v.search("doc")
        assert len(results) <= 5, "top_k par defaut = 5"


class TestConsolidate:
    """Etape 5 : consolidation hors ligne (dedup + prune)."""

    def test_consolidate_dedup_same_text(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "hello world", 1.0)
        v.index_message("c1", "m2", "user", "hello world", 1.0)
        v.vectorize_pending()
        assert len(v._data["documents"]) == 2
        v.consolidate()
        stats = v.stats()
        assert stats["total"] == 1, "les 2 docs identiques doivent etre dedupes en 1"
        assert stats["dedup_estimated"] == 0

    def test_consolidate_keeps_max_weight_on_dedup(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "dup", 1.0)
        v.index_message("c1", "m2", "user", "dup", 1.0)
        v.adjust_weight("c1", "m2", 2.0)  # m2 -> 3.0
        v.vectorize_pending()
        v.consolidate()
        doc = v._data["documents"][0]
        assert doc["metadata"]["weight"] == 3.0, "fusionne en gardant le poids max"

    def test_consolidate_prune_low_weight_old(self):
        v = VectorService(_FakeInference())
        old_ts = 1.0  # epoch tres ancien (age > grace de 720h)
        v.index_message("c1", "m_low", "user", "bad", old_ts)
        v.index_message("c1", "m_good", "user", "good", 1.0)
        v.adjust_weight("c1", "m_low", -4.0)  # weight -> -3.0 (<= -2.0, eligible)
        v.adjust_weight("c1", "m_good", 1.0)  # weight -> 2.0
        v.vectorize_pending()
        v.consolidate()
        texts = [d["text"] for d in v._data["documents"]]
        assert "bad" not in texts, "doc a poids bas et ancien doit etre prune"
        assert "good" in texts

    def test_consolidate_does_not_prune_recent(self):
        v = VectorService(_FakeInference())
        import time
        recent_ts = time.time()  # moins de 720h -> pas eligible prune meme si poids bas
        v.index_message("c1", "m_low", "user", "recent bad", recent_ts)
        v.adjust_weight("c1", "m_low", -3.0)  # weight -> -2.0
        v.vectorize_pending()
        v.consolidate()
        texts = [d["text"] for d in v._data["documents"]]
        assert "recent bad" in texts, "doc recent ne doit pas etre prune (delai de grace non atteint)"

    def test_consolidate_caps_store_size(self, monkeypatch):
        """L'index vectoriel doit rester borne meme au-dela de MAX_VECTOR_DOCS."""
        import config.constants as _const
        monkeypatch.setattr(_const, "MAX_VECTOR_DOCS", 10)
        v = VectorService(_FakeInference())
        for i in range(30):
            v.index_message("c", f"m{i}", "user", f"msg {i}", float(i))
        v.vectorize_pending()
        assert len(v._data["documents"]) > 10
        v.consolidate()
        assert len(v._data["documents"]) <= 10, "store non borne apres consolidation"

    def test_consolidate_sets_metadata(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "hello", 1.0)
        v.vectorize_pending()
        stats = v.stats()
        assert stats["consolidation_runs"] == 0
        v.consolidate()
        stats = v.stats()
        assert "last_consolidation" in stats
        assert stats["consolidation_runs"] == 1
        assert stats["last_consolidation"] > 0.0

    def test_consolidate_fuses_paraphrases(self):
        """Deux textes differents mais semantiquement proches -> fusion cosinus."""
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "bonjour le monde", 1.0)
        v.index_message("c1", "m2", "user", "bonjour le monde!", 1.0)
        v.vectorize_pending()
        assert len(v._data["documents"]) == 2
        v.consolidate()
        stats = v.stats()
        assert stats["total"] == 1, (
            "paraphrases semantiquement proches doivent etre fusionnees par cosinus"
        )
        assert stats["dedup_estimated"] == 0


class TestStatsObservability:
    """Etape 6 : champs d'observabilite dans stats()."""

    def test_stats_includes_consolidation_fields(self):
        v = VectorService(_FakeInference())
        stats = v.stats()
        assert "message_indexed" in stats
        assert "dedup_estimated" in stats
        assert "last_consolidation" in stats
        assert "consolidation_runs" in stats
        assert stats["dedup_estimated"] == 0

    def test_dedup_estimated_counts_duplicates(self):
        v = VectorService(_FakeInference())
        v.index_message("c1", "m1", "user", "same text", 1.0)
        v.index_message("c1", "m2", "user", "same text", 1.0)
        v.index_message("c1", "m3", "user", "unique", 1.0)
        stats = v.stats()
        assert stats["dedup_estimated"] == 1  # 2 docs "same text" -> 1 en trop
