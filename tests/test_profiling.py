"""Tests du profiling des endpoints lents (AUDIT-P3.2).

Vérifie que le middleware slow_endpoint_profiler détecte les requêtes
lentes, les log, et les expose dans /api/status (slow_endpoints).
ATTENTION: les patches globaux de _check_ollama sont nettoyés en fin
de fichier pour ne pas polluer les autres tests (cf. test_wave_a.py).
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import controllers.context as ctx
import controllers.router as _router_mod  # noqa: E402
from services import profiling

# Sauvegarde pour cleanup en fin de module
_ORIG_CTX_CHECK = ctx._check_ollama
_ORIG_ROUTER_CHECK = _router_mod._check_ollama


class FakeInference:
    def is_available(self, model): return True
    def query(self, prompt, model, **kw): return {"response": "ok", "model": model}
    def query_multimodal(self, model, task, image): return {"response": "vision ok", "model": model}
    def embed(self, texts): return [[0.0] * 384 for _ in texts]
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
    def index_batch(self, pairs): pass
    def vectorize_pending(self): return 0
    def stats(self): return {"documents": 0, "chunks": 0, "pending": 0}
    def search(self, q, top_k=5): return []


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
    def delete(self, conv_id):
        self._store.pop(conv_id, None)
        self._index["conversations"] = [c for c in self._index["conversations"] if c["id"] != conv_id]
    def delete_all(self):
        self._store.clear()
        self._index["conversations"] = []
    def is_healthy(self): return True


class FakeAgent:
    def run(self, task, model, context=None):
        return {"response": "ok", "agent": "test", "model": model, "backend": "ollama"}


def _apply_mocks():
    """Injecte les fakes et resynchronise les globals module-level.

    Autouse car test_api.py (qui tourne avant dans la suite) restaure les
    vrais services dans son teardown (initialize()), ce qui écrase nos mocks.
    On les ré-applique avant chaque test pour rester isolé.
    """
    # Injection des fakes avant la construction de l'app (court-circuite initialize)
    ctx._ctx._initialized = True
    ctx._ctx.inference = FakeInference()
    ctx._ctx.memory = FakeMemory()
    ctx._ctx.vector = FakeVector()
    ctx._ctx.conversations = FakeConversation()
    ctx._ctx.agents = {k: FakeAgent() for k in ("cyber", "dev", "network", "hardware", "vision")}
    ctx._ctx.log = MagicMock()  # capte les appels log du middleware
    ctx._ctx.analytics = MagicMock()
    ctx._ctx.router_svc = MagicMock()
    ctx._ctx.orchestrator = MagicMock()
    ctx._ctx.orchestrator.handle_request.return_value = {"response": "ok"}
    ctx._ctx.metrics = MagicMock()
    ctx._sync_module_globals(ctx._ctx)

    # Évite l'appel réseau httpx réel de _check_ollama dans le route /api/status
    # (qui bloque sous TestClient) ; le profiling n'en dépend pas.
    ctx._check_ollama = lambda: False
    _router_mod._check_ollama = lambda: False


# Injection initiale des fakes avant la construction de l'app
_apply_mocks()

from controllers.router import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    """Réapplique les mocks avant chaque test (isolation vis-à-vis de test_api)."""
    app.state.context = ctx._ctx
    _apply_mocks()
    profiling.reset_profiling()
    yield
    profiling.reset_profiling()


@pytest.fixture
def fast_threshold():
    """Seuil > 1s : une requête rapide ne doit pas être considérée lente."""
    old = profiling.SLOW_THRESHOLD
    profiling.SLOW_THRESHOLD = 2.0
    yield
    profiling.SLOW_THRESHOLD = old


@pytest.fixture
def zero_threshold():
    """Seuil à 0s : toute requête est considérée lente."""
    old = profiling.SLOW_THRESHOLD
    profiling.SLOW_THRESHOLD = 0.0
    yield
    profiling.SLOW_THRESHOLD = old


class TestSlowProfiler:
    def test_route_lente_apparait_dans_status(self, zero_threshold):
        # Requête rapide en temps réel, mais seuil à 0 => considérée lente
        resp = client.get("/api/jarvis")
        assert resp.status_code == 200
        # /api/status expose la route dans slow_endpoints
        status = client.get("/api/status").json()["data"]
        routes = [e["route"] for e in status["slow_endpoints"]]
        assert "/api/jarvis" in routes

    def test_requete_rapide_non_lente(self, fast_threshold):
        profiling.reset_profiling()
        resp = client.get("/api/jarvis")
        assert resp.status_code == 200
        status = client.get("/api/status").json()["data"]
        # Aucune route lente enregistrée
        assert status["slow_endpoints"] == []

    def test_compteur_et_max_duree(self, zero_threshold):
        client.get("/api/status")
        client.get("/api/status")
        endpoints = client.get("/api/status").json()["data"]["slow_endpoints"]
        entry = next(e for e in endpoints if e["route"] == "/api/status")
        assert entry["count"] >= 2
        assert entry["max_duration"] >= 0.0

    def test_record_slow_store_threadsafe(self):
        # Vérifie directement le store en mémoire
        profiling.reset_profiling()
        profiling.record_slow("/x", 1.5)
        profiling.record_slow("/x", 3.0)
        eps = profiling.get_slow_endpoints()
        assert eps == [{"route": "/x", "max_duration": 3.0, "count": 2}]


def teardown_module(module):
    """Restaure les originaux de _check_ollama pour ne pas polluer les autres tests."""
    ctx._check_ollama = _ORIG_CTX_CHECK
    _router_mod._check_ollama = _ORIG_ROUTER_CHECK
