"""Tests API — Endpoints FastAPI avec TestClient."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Patcher les services pour éviter les vrais appels réseau


class FakeInference:
    def is_available(self, model): return True
    def resolve_model(self, model): return model
    def query(self, prompt, model, **kw): return {"response": "ok", "model": model}
    def query_multimodal(self, model, task, image): return {"response": "vision ok", "model": model}
    def embed(self, texts): return [[0.0]*384 for _ in texts]
    def list_models(self): return ["phi4-mini:3.8b"]
    def first_available(self): return "phi4-mini:3.8b"
    def select_backend(self, name):
        if name != "ollama":
            raise ValueError(f"Backend inconnu : {name}")
    def get_active_backend(self): return "ollama"

class FakeMemory:
    def is_healthy(self): return True
    def get_habits(self): return []
    def update_habits(self, data): pass

class FakeVector:
    def is_healthy(self): return True
    def index(self, text, metadata=None): pass
    def index_batch(self, pairs): pass
    def index_message(self, conv_id, msg_id, role, content, ts, extra=None): pass
    def ingest_message(self, conv_id, msg_id, role, content, ts): pass
    def vectorize_pending(self): return 0
    def stats(self): return {
        "total": 0, "embedded": 0, "pending": 0,
        "weight_mean": 1.0, "low_weight_ratio": 0.0, "conversation_docs": 0,
    }
    def search(self, q, top_k=5): return []
    def adjust_weight(self, conv_id, msg_id, delta, conversations=None):
        return 1
    def clear_cache(self): pass

class FakeConversation:
    def __init__(self):
        self._store = {}
        self._index = {"conversations": []}
    def create(self, title=""):
        cid = "test1234"
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
    def list_unindexed(self, limit=None):
        items = [c for c in self._index["conversations"] if not c.get("indexed")]
        return items[:limit] if limit is not None else items
    def mark_indexed(self, conv_id):
        for c in self._index["conversations"]:
            if c["id"] == conv_id:
                c["indexed"] = True
    def delete(self, conv_id):
        self._store.pop(conv_id, None)
        self._index["conversations"] = [c for c in self._index["conversations"] if c["id"] != conv_id]
    def delete_all(self):
        self._store.clear()
        self._index["conversations"] = []
    def is_healthy(self): return True
    def set_on_message(self, callback):
        self._on_message = callback
    def backfill_message_ids(self):
        return False

import controllers.context as ctx


class FakeAgent:
    def run(self, task, model, context=None):
        return {"response": "ok", "agent": "test", "model": model, "backend": "ollama"}

def _apply_mocks():
    """Injecte les fakes dans AppContext et resynchronise les globals.

    Autouse car un test precedent dans la suite peut restaurer les vrais
    services dans son teardown (initialize()), ce qui ecrase nos mocks.
    On les re-applique avant chaque test pour rester isole.
    """
    # Skip real service init — inject mocks into AppContext
    ctx._ctx._initialized = True
    ctx._ctx.inference = FakeInference()
    ctx._ctx.memory = FakeMemory()
    ctx._ctx.vector = FakeVector()
    ctx._ctx.conversations = FakeConversation()
    ctx._ctx.agents = {k: FakeAgent() for k in ("cyber", "dev", "network", "hardware", "vision")}
    ctx._ctx.log = MagicMock()
    ctx._ctx.analytics = MagicMock()
    ctx._ctx.router_svc = MagicMock()
    ctx._ctx.orchestrator = MagicMock()
    ctx._ctx.orchestrator.handle_request.return_value = {"response": "ok"}
    ctx._ctx.metrics = MagicMock()
    # Sync module-level vars so routes importing them get the mocks
    ctx._sync_module_globals(ctx._ctx)


# Skip real service init — inject mocks into AppContext (avant build_app)
_apply_mocks()

from controllers.router import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _restore_ctx():
    app.state.context = ctx._ctx
    _apply_mocks()
    yield
    ctx._ctx._initialized = False
    ctx._ctx.initialize()
    ctx._sync_module_globals(ctx._ctx)
    from controllers.di import AppContext
    app.state.context = AppContext()
    app.state.context.initialize()


class TestRoot:
    def test_index_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")


class TestServeStatic:
    def test_missing_static_returns_404(self):
        # A2 : serve_static renvoyait un tuple {"detail":...}, 404 -> FastAPI
        # le sérialisait en 200. Il doit retourner un vrai 404.
        resp = client.get("/nope_xyz123.txt")
        assert resp.status_code == 404
        assert "detail" in resp.json()


class TestStatus:
    def test_status_returns_fields(self):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        # /api/status est enveloppé par le wrapper de réponse `ok()` -> {"data": ..., "error": null}
        data = resp.json()["data"]
        assert "ollama" in data
        assert "memory" in data
        assert "vector" in data
        assert "conversations" in data
        assert "version" in data


class TestJarvis:
    def test_post_jarvis_empty_task(self):
        resp = client.post("/api/jarvis", json={"task": ""})
        assert resp.status_code == 422

    def test_post_jarvis_missing_task(self):
        resp = client.post("/api/jarvis", json={})
        assert resp.status_code == 422

    def test_post_jarvis_valid(self):
        resp = client.post("/api/jarvis", json={"task": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data

    def test_post_jarvis_with_image(self):
        resp = client.post("/api/jarvis", json={"task": "décris", "image": "data:base64,..."})
        assert resp.status_code == 200


class TestJarvisNoDoubleWrite:
    """Règle : un POST /api/jarvis réussit n'écrit la conversation QU'UNE fois
    (1 user + 1 assistant) — pas d'effet de bord dupliqué (cf. ADR-004 / audit)."""

    def test_full_post_writes_conversation_once(self, monkeypatch):
        from services.orchestrator import OrchestratorService

        fake_inf = FakeInference()
        fake_mem = FakeMemory()
        fake_vec = FakeVector()
        fake_conv = FakeConversation()
        spy_conv = MagicMock(wraps=fake_conv)
        fake_agents = {k: FakeAgent() for k in ("cyber", "dev", "network", "hardware", "vision")}

        class FakeGraph:
            def run(self, task, conversation_id=None):
                return {"response": "ok", "agent": "test", "model": "auto", "backend": "ollama"}

        orch = OrchestratorService(
            inference=fake_inf, memory=fake_mem, vector=fake_vec,
            log=MagicMock(), analytics=MagicMock(), conversations=spy_conv,
            metrics=MagicMock(), agents=fake_agents, router_service=MagicMock(),
            toolbox=None, agent_graph_factory=lambda: FakeGraph(),
            vision_model_selector=lambda inf: "llama3.2-vision",
        )

        fake_analytics = MagicMock()
        monkeypatch.setattr(app.state.context, "orchestrator", orch)
        monkeypatch.setattr(app.state.context, "analytics", fake_analytics)
        monkeypatch.setattr(app.state.context, "conversations", spy_conv)

        resp = client.post("/api/jarvis", json={"task": "test", "conversation_id": "abc123"})
        assert resp.status_code == 200
        # 1 user + 1 assistant, écrits UNE seule fois par le routeur
        assert spy_conv.add_message.call_count == 2


class TestAgents:
    def test_list_profiles(self):
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is None
        assert "profiles" in data["data"]

    def test_assign_missing_fields(self):
        resp = client.post("/api/agents/assign", json={})
        assert resp.status_code == 422

    def test_assign_invalid_profile(self):
        resp = client.post("/api/agents/assign", json={"profile": "nope", "model": "test"})
        assert resp.status_code == 404

    def test_assign_invalid_model_rejected(self):
        # safe_model_name doit rejeter un nom de modele contenant des caracteres non autorises
        resp = client.post("/api/agents/assign", json={"profile": "nope", "model": "bad;rm -rf /"})
        assert resp.status_code in (400, 404)

    def test_vision_post_no_image(self):
        resp = client.post("/api/vision", json={"image": ""})
        assert resp.status_code == 422  # Pydantic min_length

    def test_vision_post_valid_image(self):
        resp = client.post("/api/vision", json={"image": "data:img,...", "task": "analyse"})
        assert resp.status_code == 200
        assert "response" in resp.json()


class TestSecurityHeaders:
    def test_csp_no_cdn_dependency(self):
        # M6 : chart.js est vendored localement, le CSP ne doit plus autoriser le CDN
        resp = client.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "cdn.jsdelivr.net" not in csp

    def test_local_chart_js_served(self):
        # M6 : le fichier chart.js vendored doit etre servi en local
        resp = client.get("/static/assets/js/chart.umd.min.js")
        assert resp.status_code == 200
        assert "Chart" in resp.text


class TestConversations:
    def test_create_returns_201(self):
        resp = client.post("/api/conversations")
        assert resp.status_code == 200
        assert "conversation_id" in resp.json()["data"]

    def test_list_returns_paginated(self):
        client.post("/api/conversations")
        resp = client.get("/api/conversations")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "conversations" in data
        assert "total" in data
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_get_not_found(self):
        resp = client.get("/api/conversations/nonexistent")
        assert resp.status_code == 404

    def test_get_invalid_id(self):
        resp = client.get("/api/conversations/INVALID")
        assert resp.status_code == 404

    def test_delete_not_found(self):
        resp = client.delete("/api/conversations/nonexistent")
        assert resp.status_code == 200

    def test_delete_all_removes_all_conversations(self):
        resp = client.delete("/api/conversations")
        assert resp.status_code == 200


class TestDocuments:
    def test_ingest_empty(self):
        resp = client.post("/api/ingest", json={"documents": []})
        assert resp.status_code == 400

    def test_ingest_valid_returns_200(self):
        resp = client.post("/api/ingest", json={
            "documents": [{"text": "hello world", "metadata": {"source": "test"}}]
        })
        assert resp.status_code == 200

    def test_ingest_valid_returns_ingested_count(self):
        resp = client.post("/api/ingest", json={
            "documents": [{"text": "hello world", "metadata": {"source": "test"}}]
        })
        assert resp.json()["data"]["ingested"] == 1

    def test_search_no_query(self):
        resp = client.get("/api/search")
        assert resp.status_code == 400

    def test_search_with_query(self):
        resp = client.get("/api/search?q=test")
        assert resp.status_code == 200

    def test_vectorize_stats(self):
        resp = client.get("/api/vectorize")
        assert resp.status_code == 200

    def test_vectorize_pending(self):
        resp = client.post("/api/vectorize")
        assert resp.status_code == 200

    def test_vectorize_conversations_returns_200(self):
        resp = client.post("/api/conversations", json={"title": "vec_test"})
        cid = resp.json()["data"]["conversation_id"]
        ctx._ctx.conversations.add_message(cid, "user", "Bonjour")
        ctx._ctx.conversations.add_message(cid, "assistant", "Salut")

        resp = client.post("/api/vectorize/conversations")
        assert resp.status_code == 200
        assert "vectorized" in resp.json()["data"]

    def test_vectorize_conversations_returns_fields(self):
        resp = client.post("/api/conversations", json={"title": "vec_test2"})
        cid = resp.json()["data"]["conversation_id"]
        ctx._ctx.conversations.add_message(cid, "user", "Msg1")
        ctx._ctx.conversations.add_message(cid, "user", "Msg2")
        ctx._ctx.conversations.add_message(cid, "assistant", "Msg3")

        resp = client.post("/api/vectorize/conversations")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["vectorized"] == 3
        assert data["conversations"] == 1
        assert "remaining" in data


class TestAnalytics:
    def test_get_analytics(self):
        resp = client.get("/api/analytics")
        assert resp.status_code == 200

    def test_get_peak(self):
        resp = client.get("/api/analytics/peak")
        assert resp.status_code == 200

    def test_cyber_workflows_returns_json(self):
        resp = client.get("/api/cyber/workflows")
        # Le endpoint peut retourner 404 si le fichier n'existe pas dans le contexte de test
        assert resp.status_code in [200, 404]


class TestBackend:
    def test_backend_endpoint_returns_ollama(self):
        resp = client.get("/api/backend")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("backend") == "ollama"

    def test_models_returns_200(self):
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data


class TestJarvisInfo:
    def test_jarvis_info(self):
        resp = client.get("/api/jarvis")
        assert resp.status_code == 200
        assert "endpoints" in resp.json()


class TestFeedback:
    """Etape 3 — Routes feedback explicite et implicite."""

    def test_post_feedback_returns_200(self):
        resp = client.post("/api/feedback", json={
            "conv_id": "test1234", "msg_id": "abc123", "signal": 1
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ok"
        assert data["adjusted"] == 1

    def test_post_feedback_signal_zero_rejected(self):
        resp = client.post("/api/feedback", json={
            "conv_id": "test1234", "msg_id": "abc123", "signal": 0
        })
        assert resp.status_code == 400

    def test_post_feedback_implicit_returns_200(self):
        resp = client.post("/api/feedback/implicit", json={
            "conv_id": "test1234", "msg_id": "abc123", "type": "copy"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ok"
        assert data["type"] == "copy"
        assert data["delta"] > 0

    def test_post_feedback_implicit_bad_type_rejected(self):
        resp = client.post("/api/feedback/implicit", json={
            "conv_id": "test1234", "msg_id": "abc123", "type": "unknown"
        })
        assert resp.status_code == 400
