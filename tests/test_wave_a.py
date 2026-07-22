"""TDD — Vague A : correctifs P0 (bugs/intégrité) issus du débat d'équipe.

Chaque test fige le comportement SOUHAITÉ ; ils échouent sur le code buggé et
passent après correctif. Voir synthèse du débat (orchestrateur).
"""
from unittest.mock import MagicMock

import pytest

from controllers import context as _context

# test_profiling.py patche globalement controllers.context._check_ollama (sans
# cleanup monkeypatch) -> on capture la vraie fonction à l'import pour la
# restaurer dans nos tests A4 et éviter la pollution inter-tests.
REAL_CHECK_OLLAMA = _context._check_ollama


# ---------------------------------------------------------------------------
# A1 — Double sauvegarde conversation (save_results + _save_conv)
# ---------------------------------------------------------------------------
def test_no_double_conversation_write_on_request(tmp_path):
    from controllers.routes.jarvis import _save_conv
    from services.conversation import ConversationService
    from services.pipeline_steps import save_results

    conv = ConversationService(storage_dir=str(tmp_path))
    cid = conv.create()

    class _Mem:
        def update_habits(self, *a, **k):
            pass

    class _Vec:
        def index(self, *a, **k):
            pass

        def vectorize_pending(self, *a, **k):
            pass

    state = {
        "response": "reponse", "task": "task", "agent_key": "dev",
        "result": {"backend": "ollama"}, "model": "m", "conversation_id": cid,
    }
    # Pipeline (save_results) : ne persiste PLUS la conversation (bug #1 corrigé)
    save_results(state, _Mem(), _Vec())
    # Route (_save_conv) : unique point de persistance
    _save_conv(cid, "task", {"response": "reponse", "agent": "dev", "model": "m"},
               "dev", conv)

    msgs = conv.get_conversation(cid)["messages"]
    roles = [m["role"] for m in msgs]
    assert roles.count("user") == 1
    assert roles.count("assistant") == 1
    assert len(msgs) == 2


# ---------------------------------------------------------------------------
# A2 — serve_static renvoie un vrai 404 (pas un tuple sérialisé en 200)
# (testé via TestClient dans test_api.TestServeStatic)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# A3 — embed() : IndexError non catché sur embeddings vides
# ---------------------------------------------------------------------------
def test_embed_empty_embeddings_raises(monkeypatch):
    from services.adapters.ollama_adapter import OllamaAdapter

    a = OllamaAdapter(base_url="http://x")
    monkeypatch.setattr(a, "_call_with_retry",
                        lambda *a, **k: {"embeddings": []})
    with pytest.raises(RuntimeError):
        a.embed("texte")


# ---------------------------------------------------------------------------
# A4 — _check_ollama ignore le port système 11434 (design portable)
# ---------------------------------------------------------------------------
def test_check_ollama_ignores_system_port(monkeypatch):
    import httpx

    from controllers import context

    def _fake_get(url, timeout=2):
        if ":11436" in url:
            raise httpx.ConnectError("portable down")
        if ":11434" in url:
            class _R:
                status_code = 200
            return _R()
        raise httpx.ConnectError("?")

    monkeypatch.setattr(httpx, "get", _fake_get)
    monkeypatch.setattr(context, "_check_ollama", REAL_CHECK_OLLAMA)
    # Seul le système (11434) répond : on doit retourner False (on l'ignore)
    assert context._check_ollama() is False


def test_check_ollama_ok_when_portable_up(monkeypatch):
    import httpx

    from controllers import context

    def _fake_get(url, timeout=2):
        if ":11436" in url:
            class _R:
                status_code = 200
            return _R()
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", _fake_get)
    monkeypatch.setattr(context, "_check_ollama", REAL_CHECK_OLLAMA)
    assert context._check_ollama() is True


# ---------------------------------------------------------------------------
# A5 — write_json_atomic : flush + fsync (intégrité exFAT / clef USB)
# ---------------------------------------------------------------------------
def test_write_json_atomic_flushes_and_fsyncs(monkeypatch):
    import os

    from services import file_utils

    flushed = []
    fsynced = []

    def _fake_open(p, *a, **k):
        m = MagicMock()
        m.__enter__.return_value = m

        def _flush():
            flushed.append(p)

        m.flush.side_effect = _flush
        m.fileno.return_value = 3
        return m

    monkeypatch.setattr("builtins.open", _fake_open)
    monkeypatch.setattr(os, "fsync", lambda fd: fsynced.append(fd))
    monkeypatch.setattr(os, "replace", lambda s, d: None)

    file_utils.write_json_atomic("/tmp/x.json", {"a": 1})
    assert flushed, "flush() non appelé"
    assert fsynced, "os.fsync() non appelé"


# ---------------------------------------------------------------------------
# A6 — add_message : échec explicite (pas de return silencieux) sur conv_id invalide
# ---------------------------------------------------------------------------
def test_add_message_invalid_conv_id_raises(tmp_path):
    from services.conversation import ConversationService

    conv = ConversationService(storage_dir=str(tmp_path))
    with pytest.raises(ValueError):
        conv.add_message("bad id!", "user", "x")
    # Un conv_id valide continue de fonctionner
    cid = conv.create()
    conv.add_message(cid, "user", "ok")


# ---------------------------------------------------------------------------
# A7 — query_model : tâche vide -> erreur explicite (pas de bulle vide)
# ---------------------------------------------------------------------------
def test_query_model_empty_task_sets_error():
    from services.pipeline_steps import query_model

    state = {
        "task": "", "agent_key": "dev", "image": None, "context": {},
        "result": None, "response": "", "error": None,
    }
    fake_inf = MagicMock()
    fake_inf.first_available.return_value = "m"
    fake_agents = {"dev": MagicMock()}
    fake_toolbox = MagicMock()
    fake_toolbox.is_enabled.return_value = False

    out = query_model(state, fake_inf, fake_agents, fake_toolbox, lambda *a: "m")
    assert out["error"] is not None
    assert out["response"] != ""


# ---------------------------------------------------------------------------
# A8 — select_model : "" au lieu de "auto" si rien n'est disponible
# ---------------------------------------------------------------------------
def test_select_model_returns_empty_when_none_available():
    from services.selector import select_model

    class _Inf:
        def resolve_model(self, m):
            return None

        def first_available(self):
            return None

    assert select_model("dev", _Inf()) == ""
    assert select_model("vision", _Inf()) == ""


# ---------------------------------------------------------------------------
# A9 — _start_ollama_backend : code mort ? VÉRIFIÉ, non reproductible.
# Les lignes "Echec demarrage"/"absent" sont ATTEIGNABLES (binaire présent/échec
# vs binaire absent). Pas de correctif nécessaire.
# ---------------------------------------------------------------------------
