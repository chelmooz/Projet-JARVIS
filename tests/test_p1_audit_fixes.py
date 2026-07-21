"""TDD — Correctifs P1 confirmés (audit GO/NO-GO v5.3/5.4, verification source du 21/07/2026).

Sur les 8 P1 releves par l'audit, 6 etaient des faux positifs (deja corriges
en amont : port_manager LISTENING, launcher tar/tmp, router 404, base.py
_profile_cache, log.py raw_decode, vector.py lock d'instance). Seuls #4 et #8
sont reels et sont couverts ici.

Chaque test fige le comportement SOUHAITE ; ils echouent sur le code buggue
et passent apres correctif (RED -> GREEN).
"""
import json
import os
import sys
import time
from unittest.mock import MagicMock

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)


# ---------------------------------------------------------------------------
# P1 #4 — read_preferences() : I/O disque a chaque appel, sans cache (clef USB)
# ---------------------------------------------------------------------------
class TestReadPreferencesCache:

    def _reload_selector(self, monkeypatch, prefs_path):
        """Recharge services.selector avec PREFERENCES_PATH pointant sur un fichier temporaire."""
        import importlib

        import services.selector as selector
        importlib.reload(selector)
        monkeypatch.setattr(selector, "PREFERENCES_PATH", str(prefs_path))
        return selector

    def test_second_call_does_not_reread_file_when_mtime_unchanged(self, tmp_path, monkeypatch):
        prefs_path = tmp_path / "model_preferences.json"
        prefs_path.write_text(json.dumps({"offline": False}), encoding="utf-8")
        selector = self._reload_selector(monkeypatch, prefs_path)

        real_open = open
        call_count = {"n": 0}

        def _counting_open(path, *a, **k):
            if str(path) == str(prefs_path):
                call_count["n"] += 1
            return real_open(path, *a, **k)

        monkeypatch.setattr("builtins.open", _counting_open)

        selector.read_preferences()
        selector.read_preferences()
        selector.read_preferences()

        assert call_count["n"] == 1, (
            f"read_preferences() a rouvert le fichier {call_count['n']} fois "
            "sans que son mtime ait change (cache absent)"
        )

    def test_cache_invalidates_when_file_changes(self, tmp_path, monkeypatch):
        prefs_path = tmp_path / "model_preferences.json"
        prefs_path.write_text(json.dumps({"offline": False}), encoding="utf-8")
        selector = self._reload_selector(monkeypatch, prefs_path)

        first = selector.read_preferences()
        assert first == {"offline": False}

        # mtime distinct garanti (certains FS ont une resolution de 1s)
        time.sleep(0.01)
        new_mtime = os.path.getmtime(prefs_path) + 1
        prefs_path.write_text(json.dumps({"offline": True}), encoding="utf-8")
        os.utime(prefs_path, (new_mtime, new_mtime))

        second = selector.read_preferences()
        assert second == {"offline": True}, "le cache n'a pas ete invalide apres modification du fichier"


# ---------------------------------------------------------------------------
# P1 #8 — _track_query : tokens_in calcule sur la reponse au lieu de la tache
# ---------------------------------------------------------------------------
class TestTrackQueryTokens:

    def test_tokens_in_reflects_task_not_response(self):
        from controllers.routes.jarvis import _track_query

        task = "a" * 400  # ~100 tokens
        result = {"response": "b" * 40, "error": None}  # ~10 tokens
        analytics = MagicMock()

        _track_query("dev", "qwen2.5", result, time.time(), analytics, task=task)

        _, kwargs = analytics.track_query.call_args
        assert kwargs["tokens_in"] == len(task) // 4, (
            "tokens_in doit etre derive de la tache envoyee, pas de la reponse"
        )
        assert kwargs["tokens_out"] == len(result["response"]) // 4
        assert kwargs["tokens_in"] != kwargs["tokens_out"]
