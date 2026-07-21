"""Tests for POST /api/vectorize/conversations (P6 A1-A5)."""

import pytest
from fastapi.testclient import TestClient

import controllers.context as _ctx_module


@pytest.fixture
def client():
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from controllers.router import app
    return TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def _isolate_context():
    """Re-initialise le vrai contexte applicatif pour ce module, indépendamment
    de la pollution globale d'autres fichiers (ex: test_api restore des singletons
    a None/MagicMock dans son teardown). Garantit que les routes utilisent les
    vrais services (conversations, vector, analytics) — necessaire pour C1 et le
    cleanup des conversations.
    """
    _ctx_module._ctx._initialized = False
    _ctx_module._ctx.initialize()
    _ctx_module._sync_module_globals(_ctx_module._ctx)
    yield
    # Laisser le vrai contexte en place (etat correct).


@pytest.fixture(autouse=True)
def cleanup(client):
    """Nettoie les conversations avant chaque test pour isoler l'état du singleton."""
    client.delete("/api/conversations")
    yield


def _create_conversation(client, title, msg_count=1):
    resp = client.post("/api/conversations", json={"title": title})
    assert resp.status_code == 200
    cid = resp.json()["conversation_id"]
    for i in range(msg_count):
        resp = client.post(f"/api/conversations/{cid}/messages", json={
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i} for {title}"
        })
        assert resp.status_code == 200
    return cid


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


class TestFallbackHistogram:

    def test_fallback_histogram_dim(self, client):
        """A3: si l'embedding Ollama echoue, repli histogramme de dimension 16."""
        from services.vector import VectorService

        svc = VectorService()
        svc._inference = _FailingInference()

        emb = svc._embed("texte de test pour le repli")
        assert len(emb) == 16, f"Fallback doit faire 16 dims, got {len(emb)}"
        assert svc._using_fallback is True
        assert abs(sum(emb) - 1.0) < 1e-6


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
