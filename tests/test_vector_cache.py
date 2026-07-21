"""Tests VectorService et VectorCache — Cache LRU, TTL horodaté et invalidation."""
import pytest

from controllers import context as ctx_mod
from services import vector as vector_mod
from services.vector import VECTOR_CACHE_TTL_SECONDS, VectorService
from services.vector_cache import VectorCache


@pytest.fixture(autouse=True)
def _isolated_index(tmp_path, monkeypatch):
    """Isole l'index vectoriel sur disque et force le fallback embedding
    deterministe (ctx.inference=None) pour eviter la contamination inter-tests
    via l'etat global partage."""
    monkeypatch.setattr(vector_mod, "VECTOR_PATH", str(tmp_path / "vector_index.json"))
    monkeypatch.setattr(ctx_mod._ctx, "inference", None)


class TestVectorCache:
    def test_put_then_get(self):
        cache = VectorCache()
        cache.put("salut", 1, [{"text": "a", "score": 0.9}], now=1000.0)
        assert cache.get("salut", 1, now=1000.0) == [{"text": "a", "score": 0.9}]
        assert cache.hits == 1
        assert cache.misses == 0

    def test_get_missing_returns_none(self):
        cache = VectorCache()
        assert cache.get("inconnu", 1, now=1000.0) is None
        assert cache.misses == 1

    def test_get_different_top_k_misses(self):
        cache = VectorCache()
        cache.put("salut", 1, [{"text": "a"}], now=1000.0)
        assert cache.get("salut", 2, now=1000.0) is None

    def test_ttl_expiration(self):
        cache = VectorCache(ttl_seconds=300)
        cache.put("salut", 1, [{"text": "a"}], now=1000.0)
        # Limite exacte du TTL : encore valide
        assert cache.get("salut", 1, now=1000.0 + 300) is not None
        # Au-delà du TTL : entrée purgée et recalcul nécessaire
        assert cache.get("salut", 1, now=1000.0 + 301) is None
        assert len(cache) == 0

    def test_clear(self):
        cache = VectorCache()
        cache.put("salut", 1, [{"text": "a"}], now=1000.0)
        cache.clear()
        assert len(cache) == 0
        assert cache.get("salut", 1, now=1000.0) is None

    def test_lru_max_size(self):
        cache = VectorCache(max_size=2)
        cache.put("a", 1, [{"text": "a"}], now=1.0)
        cache.put("b", 1, [{"text": "b"}], now=2.0)
        cache.put("c", 1, [{"text": "c"}], now=3.0)
        assert len(cache) == 2
        # Le plus ancien (a) a été évincé
        assert cache.get("a", 1, now=3.0) is None
        assert cache.get("c", 1, now=3.0) is not None

    def test_lru_move_to_end_on_hit(self):
        cache = VectorCache(max_size=2)
        cache.put("a", 1, [{"text": "a"}], now=1.0)
        cache.put("b", 1, [{"text": "b"}], now=2.0)
        cache.get("a", 1, now=3.0)  # remet 'a' en fin de file
        cache.put("c", 1, [{"text": "c"}], now=4.0)  # évince 'b'
        assert cache.get("a", 1, now=4.0) is not None
        assert cache.get("b", 1, now=4.0) is None

    def test_index_batch_clears_cache(self):
        v = VectorService()
        v.index("doc alpha", {"source": "test"})
        v.vectorize_pending()
        # Remplir le cache
        v.search("doc", top_k=1)
        assert len(v._cache) == 1
        # Force l'ajout pour isoler le test de l'index disque partagé
        v._exists = lambda text: False
        # Indexation suivante doit vider le cache
        v.index_batch([("doc beta", {"source": "test"})])
        assert len(v._cache) == 0
        assert v.search("doc", top_k=1)  # nouveau résultat cohérent

    def test_clear_cache_public(self):
        v = VectorService()
        v.index("doc gamma", {"source": "test"})
        v.vectorize_pending()
        v.search("doc", top_k=1)
        assert len(v._cache) == 1
        v.clear_cache()
        assert len(v._cache) == 0

    def test_cache_entry_expires_after_ttl(self):
        v = VectorService()
        v.index("doc delta", {"source": "test"})
        v.vectorize_pending()
        now = [1000000.0]

        def fake_now():
            return now[0]

        v._now = fake_now
        r1 = v.search("doc", top_k=1)
        assert len(v._cache) == 1
        # Avant expiration : hit
        r2 = v.search("doc", top_k=1)
        assert r1 == r2
        # Après expiration : l'entrée est rejetée et recalculée
        now[0] += VECTOR_CACHE_TTL_SECONDS + 1
        r3 = v.search("doc", top_k=1)
        assert r1 == r3
        # L'ancienne entrée expirée a été purgée
        assert len(v._cache) == 1
        # Le hit n'a pas augmenté (entrée expirée = miss puis re-cache)
        assert v._cache_hits == 1

    def test_search_hits_cache_twice(self):
        v = VectorService()
        v.index("doc epsilon", {"source": "test"})
        v.vectorize_pending()
        now = [2000000.0]
        v._now = lambda: now[0]
        r1 = v.search("doc", top_k=1)
        r2 = v.search("doc", top_k=1)
        assert r1 == r2
        assert v._cache_hits == 1
        assert v._cache_misses == 1
