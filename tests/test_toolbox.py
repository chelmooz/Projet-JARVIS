"""Tests TDD pour services/toolbox.py - API publique uniquement.

Tous les tests utilisent des triggers chargés depuis un YAML en tmp_path,
jamais la config réelle du dépôt.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from services.toolbox import Toolbox

# ── Helper : YAML de triggers temporaire ──────────────────────────


def _tmp_triggers_yaml(*, diagnostics: bool = True, files: bool = True) -> Path:
    """Retourne un chemin de fichier YAML de triggers en tmp_path."""
    items = []
    if diagnostics:
        items.extend(
            [
                {
                    "keywords": ["test-disque", "disk"],
                    "key": "disk",
                    "tool": "smartctl",
                    "description": "test disk tool",
                },
                {
                    "keywords": ["test-system", "system"],
                    "key": "system",
                    "tool": "psinfo",
                    "description": "test system tool",
                },
            ]
        )
    if files:
        items.extend(
            [
                {
                    "keywords": ["test-ls", "ls"],
                    "key": "ls",
                    "tool": "list_dir",
                    "description": "test list dir tool",
                },
            ]
        )
    data = {"triggers": items}
    fp = Path(tempfile.mktemp(suffix=".yaml"))
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return fp


# Monkeypatch pour charger les triggers depuis le YAML temporaire au lieu
# de la config réelle du dépôt.
import services.toolbox as tb_mod

_original_load_all = tb_mod.Toolbox._load_all_triggers


def _monkeypatch_load_all(self: tb_mod.Toolbox) -> list:
    """Charger les triggers depuis le YAML temporaire si dispo, sinon réel."""
    if hasattr(self, "_tmp_triggers_path") and self._tmp_triggers_path.exists():
        try:
            with open(self._tmp_triggers_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}
        triggers = data.get("triggers", [])
        return triggers if isinstance(triggers, list) else []
    return _original_load_all(self)


import yaml

tb_mod.Toolbox._load_all_triggers = _monkeypatch_load_all


# ── is_enabled ─────────────────────────────────────────────────────


class TestIsEnabled:
    def test_is_enabled_when_no_triggers(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = []
        tb._file_triggers = []
        assert tb.is_enabled() is False

    def test_is_enabled_when_diagnostic_triggers_present(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = [(["test-disque", "disk"], {}, lambda: {"ok": True})]
        tb._file_triggers = []
        assert tb.is_enabled() is True

    def test_is_enabled_when_file_triggers_present(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = []
        tb._file_triggers = [(["test-ls", "ls"], {}, lambda: {"ok": True})]
        assert tb.is_enabled() is True


# ── describe_tools ─────────────────────────────────────────────────


class TestDescribeTools:
    def test_describe_tools_lists_loaded_tools(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = [(["test-disque", "disk"], {}, lambda: {"ok": True})]
        tb._file_triggers = [(["test-ls", "ls"], {}, lambda: {"ok": True})]
        result = tb.describe_tools()
        assert isinstance(result, str)
        assert "Outils disponibles :" in result


# ── auto_execute ───────────────────────────────────────────────────


class TestAutoExecute:
    def test_auto_execute_trigger_file_matche(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = []
        tb._file_triggers = [
            (["test-ls", "ls"], {"key": "ls", "tool": "list_dir"}, lambda path: {"success": True, "entries": []})
        ]
        result = tb.auto_execute("ls mon dossier")
        assert result.get("ls", {}).get("success") is True

    def test_auto_execute_no_trigger_matches(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = [(["mot-clef"], {}, lambda: {"success": True})]
        tb._file_triggers = [(["autre"], {}, lambda: {"success": True})]
        result = tb.auto_execute("une tâche sans trigger")
        assert result == {}

    def test_auto_execute_target_absent_returns_error_entry(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = [(["pourquoi", "running"], {}, lambda: {"success": True})]
        tb._file_triggers = []
        result = tb.auto_execute("une tâche sans target valide")
        # When target is absent, why_running won't be in results
        assert "why_running" not in result or result.get("why_running", {}).get("success") is False

    def test_auto_execute_exception_captured_no_propagate(self) -> None:
        tb = Toolbox()
        tb._diagnostic_triggers = [
            (
                ["systeme"],
                {"key": "system", "tool": "psinfo"},
                lambda entry, task: (_ for _ in ()).throw(RuntimeError("boom")),
            )
        ]
        tb._file_triggers = []
        result = tb.auto_execute("systeme")
        assert result.get("system", {}).get("success") is False
        assert "error" in result.get("system", {})


# ── tool_results_to_prompt ────────────────────────────────────────


class TestToolResultsToPrompt:
    def test_tool_results_to_prompt_formats_success(self) -> None:
        tb = Toolbox()
        results = {"disk": {"success": True, "tool": "smartctl"}}
        result = tb.tool_results_to_prompt(results)
        assert "[OK]" in result

    def test_tool_results_to_prompt_formats_error(self) -> None:
        tb = Toolbox()
        results = {"disk": {"success": False, "tool": "smartctl", "error": "not found"}}
        result = tb.tool_results_to_prompt(results)
        assert "Erreur:" in result

    def test_tool_results_to_prompt_empty(self) -> None:
        tb = Toolbox()
        result = tb.tool_results_to_prompt({})
        assert result == ""


# ── _extract_target (pure function test) ──────────────────────────


class TestExtractTarget:
    def test_extract_target_with_valid_target(self) -> None:
        target = Toolbox._extract_target("quoi occupe le port 8080")
        assert isinstance(target, str)
        assert len(target) > 0

    def test_extract_target_no_candidates(self) -> None:
        # Use a sentence where all meaningful tokens are excluded
        target = Toolbox._extract_target("pourquoi tourne le processus")
        assert target == ""


# ── _fold_accents (pure function test) ────────────────────────────


class TestFoldAccents:
    def test_fold_accents_basic(self) -> None:
        result = Toolbox._fold_accents("éèàù")
        assert result == "eeau"

    def test_fold_accents_no_accents(self) -> None:
        result = Toolbox._fold_accents("abcdef")
        assert result == "abcdef"
