Set-Content -Path fix_13.py -Encoding UTF8 -Value @'
import pathlib

# === Fix 1: test_profiling.py ===
p = pathlib.Path("tests/test_profiling.py")
c = p.read_text(encoding="utf-8")
c = c.replace("ctx.SLOW_THRESHOLD", "profiling.SLOW_THRESHOLD")
p.write_text(c, encoding="utf-8")
print("Fix 1: test_profiling.py OK")

# === Fix 2: test_search_pagination.py ===
p = pathlib.Path("tests/test_search_pagination.py")
c = p.read_text(encoding="utf-8")
c = c.replace("ctx_mod.vector", "ctx_mod._ctx.vector")
p.write_text(c, encoding="utf-8")
print("Fix 2: test_search_pagination.py OK")

# === Fix 3: test_vectorize.py ===
p = pathlib.Path("tests/test_vectorize.py")
c = p.read_text(encoding="utf-8")

# 3a: Ajouter le cablage app.state.context dans le fixture client
c = c.replace(
    'from controllers.router import app\n    return TestClient(app)',
    'from controllers.router import app\n    app.state.context = _ctx_module._ctx\n    return TestClient(app)'
)

# 3b: Remplacer _isolate_context par un fixture qui injecte des fakes
old_isolate = '''@pytest.fixture(autouse=True, scope="module")
def _isolate_context():
    """Re-initialise le vrai contexte applicatif pour ce module, independamment
    de la pollution globale d'autres fichiers (ex: test_api restore des singletons
    a None/MagicMock dans son teardown). Garantit que les routes utilisent les
    vrais services (conversations, vector, analytics) -- necessaire pour C1 et le
    cleanup des conversations.
    """
    _ctx_module._ctx._initialized = False
    _ctx_module._ctx.initialize()
    _ctx_module._sync_module_globals(_ctx_module._ctx)
    yield
    # Laisser le vrai contexte en place (etat correct).'''

new_isolate = '''@pytest.fixture(autouse=True, scope="module")
def _isolate_context():
    """Injecte des fakes dans le contexte pour ce module, comme test_api.py."""
    from unittest.mock import MagicMock

    class FakeVector:
        def is_healthy(self): return True
        def index(self, text, metadata=None): pass
        def index_batch(self, pairs): pass
        def index_message(self, conv_id, msg_id, role, content, ts, extra=None): pass
        def ingest_message(self, conv_id, msg_id, role, content, ts): pass
        def vectorize_pending(self): return 0
        def stats(self): return {"total": 0, "embedded": 0, "pending": 0, "weight_mean": 1.0, "low_weight_ratio": 0.0, "conversation_docs": 0}
        def search(self, q, top_k=5): return []
        def adjust_weight(self, conv_id, msg_id, delta, conversations=None): return 1
        def clear_cache(self): pass

    class FakeConversation:
        def __init__(self):
            self._store = {}
            self._index = {"conversations": []}
        def create(self, title=""):
            cid = f"vec_test_{len(self._index['conversations'])}"
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
        def set_on_message(self, callback): pass
        def backfill_message_ids(self): return False

    _ctx_module._ctx._initialized = True
    _ctx_module._ctx.vector = FakeVector()
    _ctx_module._ctx.conversations = FakeConversation()
    _ctx_module._ctx.inference = MagicMock()
    _ctx_module._ctx.inference.embed.return_value = [[0.0] * 384]
    _ctx_module._ctx.memory = MagicMock()
    _ctx_module._ctx.log = MagicMock()
    _ctx_module._ctx.analytics = MagicMock()
    _ctx_module._ctx.agents = {}
    _ctx_module._ctx.router_svc = MagicMock()
    _ctx_module._ctx.orchestrator = MagicMock()
    _ctx_module._ctx.metrics = MagicMock()
    _ctx_module._sync_module_globals(_ctx_module._ctx)
    yield'''

c = c.replace(old_isolate, new_isolate)
p.write_text(c, encoding="utf-8")
print("Fix 3: test_vectorize.py OK")
'@