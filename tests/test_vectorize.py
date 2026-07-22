"""Tests for POST /api/vectorize/conversations (P6 A1-A5)."""

import pytest
from fastapi.testclient import TestClient

import controllers.context as _ctx_module


class _FakeConversation:
    def __init__(self):
        self._store = {}
        self._index = {"conversations": []}
    def create(self, title=""):
        cid = "test-vectorize"
        self._store[cid] = {"id": cid, "messages": []}
        self._index["conversations"].append({"id": cid, "title": title, "created_at": 0.0})
        return cid
    def add_message(self, conv_id, role, content, **kw):
        if conv_id in self._store:
            self._store[conv_id]["messages"].append({"role": role, "content": content})
    def get_conversation(self, conv_id):
        return self._store.get(conv_id)
    def list_all(self):
        return self._index["conversations"]
    def delete(self, conv_id):
        self._store.pop(conv_id, None)
        self._index["conversations"] = [c for c in self._index["conversations"] if c["id"] != conv_id]
    def delete_all(self):
        self._store.clear()
        self._index["conversations"] = []
    def is_healthy(self): return True


class _FakeAnalytics:
    def track_query(self, *a, **kw): pass
    def get_metrics(self): return {"total_conversations": 0}
    def increment_conversations(self): pass


def _inject_fakes():
    _ctx_module._ctx._initialized = True
    _ctx_module._ctx.inference = None
    _ctx_module._ctx.conversations = _FakeConversation()
    _ctx_module._ctx.analytics = _FakeAnalytics()
    _ctx_module._ctx.vector = None
    _ctx_module._ctx.memory = None
    _ctx_module._ctx.log = None
    _ctx_module._ctx.metrics = None
    _ctx_module._ctx.agents = {}
    _ctx_module._ctx.router_svc = None
    _ctx_module._ctx.orchestrator = None


_inject_fakes()


@pytest.fixture
def client():
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from controllers.router import app
    app.state.context = _ctx_module._ctx
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup(client):
    """Nettoie les conversations avant chaque test pour isoler l'état du singleton."""
    client.delete("/api/conversations")
    yield


def _create_conversation(client, title, msg_count=1):
    resp = client.post("/api/conversations", json={"title": title})
    assert resp.status_code == 200
    cid = resp.json()["data"]["conversation_id"]
    for i in range(msg_count):
        resp = client.post(f"/api/conversations/{cid}/messages", json={
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i} for {title}"
        })
        assert resp.status_code == 200
    return cid


@pytest.mark.live
class TestLimitToFive:

    def test_lot_max_5(self, client):
        """A1: POST /api/vectorize/conversations ne traite que 5 max."""
        for i in range(6):
            _create_conversation(client, f"A1_test_{i}", msg_count=2)

        resp = client.post("/api/vectorize/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversations"] <= 5, f"Expected <=5, got {data['conversations']}"
        assert data["vectorized"] > 0
        assert "remaining" in data
        assert isinstance(data["remaining"], int)


@pytest.mark.live
class TestNonDestructive:
    """Etape 0 (audit) : vectoriser ne detruit PAS la conversation source.
    Le marqueur 'indexed' empeche le retraitement infini (idempotent)."""

    def test_vectorize_conversations_does_not_delete_source(self, client):
        """La conversation vectorisee reste presente apres vectorisation."""
        cid = _create_conversation(client, "NONDESTRUCT_test", msg_count=1)

        resp = client.post("/api/vectorize/conversations")
        assert resp.status_code == 200
        assert resp.json()["conversations"] == 1

        # La source existe toujours (liste + detail).
        ids = [c["id"] for c in client.get("/api/conversations").json()["conversations"]]
        assert cid in ids, "La conversation source ne doit pas etre supprimee"
        detail = client.get(f"/api/conversations/{cid}").json()
        assert detail.get("id") == cid

    def test_vectorize_is_idempotent(self, client):
        """Un second appel ne retraite pas les conversations deja indexees."""
        _create_conversation(client, "IDEMPOTENT_test", msg_count=1)

        client.post("/api/vectorize/conversations")
        resp2 = client.post("/api/vectorize/conversations")
        data2 = resp2.json()
        assert data2["conversations"] == 0, (
            "Les conversations deja indexees ne doivent pas etre retraitees"
        )
        assert data2.get("message", "").startswith("Aucune")


class _FailingInference:
    """Mock : simule une panne Ollama (timeout/indisponible) sur embed()."""

    def embed(self, text):
        raise RuntimeError("simulated Ollama timeout")


class TestEmbeddingFailFast:

    def test_embedding_raise_si_backend_inaccessible(self, client):
        """A3: si l'embedding Ollama echoue, Embedder leve RuntimeError (Fail-Fast)."""
        from services.vector_embedder import Embedder

        embedder = Embedder(inference_service=_FailingInference())
        with pytest.raises(RuntimeError, match="temporairement indisponible"):
            embedder.embed("texte de test")


@pytest.mark.live
class TestConcurrentNoDuplicate:

    def test_concurrent_no_duplicate(self, client):
        """A4: 2 appels concurrents ne creent pas de doublons dans le store vectoriel."""
        import threading

        from services.vector import VectorService

        # Isole le store vectoriel (persistant sur disque) pour eviter la pollution
        # des autres tests ; l'atomicite de index_batch garantit la dedup concurrente.
        vstore = _ctx_module.get_context().vector
        vstore._data["documents"] = []
        vstore._save()

        for i in range(6):
            _create_conversation(client, f"A4_test_{i}", msg_count=1)

        results = []

        def worker():
            results.append(client.post("/api/vectorize/conversations").json())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        svc = VectorService()
        texts = [d["text"] for d in svc._data["documents"]]
        # Invariant de sureté : aucun doublon de texte dans le store vectoriel
        # (garanti par la dedup de index_batch, meme en cas d'appels concurrents).
        assert len(texts) == len(set(texts)), "Doublons detectes dans le store vectoriel"


class TestVectorizeUpdatesAnalytics:

    @pytest.mark.live
    def test_vectorize_updates_analytics(self, client):
        """C1: vectoriser des conversations incremente total_conversations dans /api/analytics.

        Requiert Ollama (embedding réel) : skippé hors-ligne (fallback histogramme
        ne met pas a jour total_conversations de la meme facon).
        """
        _create_conversation(client, "C1_test", msg_count=1)

        before = client.get("/api/analytics").json().get("total_conversations", 0)

        resp = client.post("/api/vectorize/conversations")
        assert resp.status_code == 200
        assert resp.json()["conversations"] == 1

        after = client.get("/api/analytics").json().get("total_conversations", 0)
        assert after == before + 1, (
            f"total_conversations devrait passer de {before} a {before + 1}, got {after}"
        )
