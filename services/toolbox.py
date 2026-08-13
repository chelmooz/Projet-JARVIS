"""Toolbox — Boîte à outils pour les agents JARVIS.

Chaque agent peut invoquer :
  - des diagnostics externes (smartctl, Sysinternals, witr)
  - des opérations fichiers (list_dir, read_file, find_files)
Les résultats sont formatés pour être injectés dans le prompt LLM.

La liste des triggers provient de ``config/toolbox_triggers.yaml`` (source
de vérité unique) : les mots-clés et descriptions sont déclaratifs, le
mapping ``tool_name -> méthode`` est l'unique responsabilité de ce module.
"""

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from config.paths import ROOT, TRIGGERS_CONFIG
from services.diagnostic_ext import DiagnosticExtService
from services.file_system import FileSystemService

MAX_STDOUT_LENGTH = 300
MAX_CONTENT_LENGTH = 500
MAX_MATCHES = 30
MAX_ENTRIES = 50
FALLBACK_DIR: str = str(ROOT)

_Trigger = tuple[list[str], dict[str, Any], Any]

# Outils gérés par Toolbox. Les autres entrées du YAML (kill_*, code_review_*,
# quality_audit) sont censées être traitées par d'autres services ; Toolbox les
# ignore pour ne pas les exécuter par erreur.
_DIAGNOSTIC_TOOLS = {
    "smartctl": "run_smartctl",
    "psinfo": "run_psinfo",
    "psloglist": "run_psloglist",
    "handle": "run_handle",
    "psping": "run_psping",
    "psservice": "run_psservice",
    "witr": "run_witr",
}

_FILE_TOOLS = {
    "list_dir": "list_dir",
    "read_file": "read_file",
    "find_files": "find_files",
}


class Toolbox:
    """Gère les triggers, l'exécution et le formatage des résultats."""

    def __init__(
        self, diagnostic_service: DiagnosticExtService | None = None, file_service: FileSystemService | None = None
    ) -> None:
        self._diagnostic = diagnostic_service or DiagnosticExtService()
        self._file_system = file_service or FileSystemService()

        self._diagnostic_triggers = self._load_diagnostic_triggers()
        self._file_triggers = self._load_file_triggers()

    # ------------------------------------------------------------------
    # Chargement des triggers depuis le YAML (source de vérité unique)
    # ------------------------------------------------------------------

    def _load_all_triggers(self) -> list[dict[str, Any]]:
        """Charge la liste des triggers depuis `toolbox_triggers.yaml`."""
        path: Path = TRIGGERS_CONFIG
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return []
        triggers = data.get("triggers", [])
        return triggers if isinstance(triggers, list) else []

    def _load_diagnostic_triggers(self) -> list[_Trigger]:
        """Construit les triggers de diagnostic depuis le YAML."""
        triggers: list[_Trigger] = []
        for entry in self._load_all_triggers():
            tool = entry.get("tool")
            if tool not in _DIAGNOSTIC_TOOLS:
                continue
            method = _DIAGNOSTIC_TOOLS[tool]
            fn = getattr(self._diagnostic, method)
            triggers.append((list(entry.get("keywords", [])), entry, fn))
        return triggers

    def _load_file_triggers(self) -> list[_Trigger]:
        """Build list of file triggers from the YAML."""
        triggers: list[_Trigger] = []
        for entry in self._load_all_triggers():
            tool = entry.get("tool")
            if tool not in _FILE_TOOLS:
                continue
            method = _FILE_TOOLS[tool]
            fn = getattr(self._file_system, method)
            triggers.append((list(entry.get("keywords", [])), entry, fn))
        return triggers

    def is_enabled(self) -> bool:
        return bool(self._diagnostic_triggers or self._file_triggers)

    # ------------------------------------------------------------------
    # Helpers d'extraction (chemin / pattern depuis une phrase)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_path(task: str) -> str:
        """Extrait le premier chemin absolu (Win ou Linux) d'une tâche."""
        m = re.search(r'[A-Za-z]:\\[^\'"]+|/[^\'"]+', task)
        if not m:
            return FALLBACK_DIR
        path = m.group(0).rstrip(".,;:!?'\" ")
        found = os.path.abspath(path)
        if os.path.exists(found):
            return found
        parts = found.split(os.sep)
        for i in range(len(parts) - 1, 0, -1):
            candidate = os.sep.join(parts[:i])
            if os.path.exists(candidate):
                return candidate
        return FALLBACK_DIR

    @staticmethod
    def _extract_pattern(task: str) -> str:
        """Extrait le premier pattern glob d'une tâche, fallback **/*."""
        m = re.search(r'[A-Za-z]:\\[^\'"]+\.\*|/[^\'"]+\*\*', task)
        if m:
            return m.group(0)
        path = Toolbox._extract_path(task)
        return os.path.join(path, "**/*") if path else "**/*"

    # ------------------------------------------------------------------
    # Description des outils pour le prompt agent
    # ------------------------------------------------------------------

    def describe_tools(self) -> str:
        lines = ["Outils disponibles :"]
        show_files = self._file_system.list_authorized()
        for entry in self._load_all_triggers():
            tool = entry.get("tool")
            if tool in _DIAGNOSTIC_TOOLS or (show_files and tool in _FILE_TOOLS):
                lines.append(f"  - {entry.get('key')} : {entry.get('description')}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Exécution automatique : matche les mots-clés de la tâche
    # ------------------------------------------------------------------

    @staticmethod
    def _fold_accents(text: str) -> str:
        """Retire les diacritiques (é->e, è->e, ...) pour un matching robuste.

        Bug réel (déploiement clé USB, 07/08/2026) : une tâche naturelle en
        français ("état système", "événements récents") ne déclenchait
        jamais les triggers YAML ("systeme", "evenement" sans accent),
        laissant l'agent halluciner un rapport système complet faute de
        vraies données outil.
        """
        decomposed = unicodedata.normalize("NFKD", text)
        return "".join(c for c in decomposed if not unicodedata.combining(c))

    def auto_execute(self, task: str) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        lower = self._fold_accents(task.lower())
        for keywords, entry, fn in self._diagnostic_triggers + self._file_triggers:
            if any(self._fold_accents(kw) in lower for kw in keywords):
                key = entry["key"]
                tool_name = entry["tool"]
                try:
                    results[key] = self._invoke(fn, tool_name, entry, task)
                except Exception as e:
                    results[key] = {"success": False, "tool": tool_name, "error": str(e)}
        return results

    def _invoke(self, fn: Any, tool_name: str, entry: dict[str, Any], task: str) -> dict[str, Any]:
        """Appelle la méthode de l'outil avec les bons arguments (par tool)."""
        key = str(entry.get("key") or "")
        if tool_name in _FILE_TOOLS:
            return self._invoke_file(fn, key, task)
        return self._invoke_diagnostic(fn, key, task)

    def _invoke_file(self, fn: Any, key: str, task: str) -> dict[str, Any]:
        if key == "ls":
            return dict(fn(self._extract_path(task)))
        if key == "read":
            return dict(fn(self._extract_path(task)))
        if key == "find":
            return dict(fn(self._extract_pattern(task)))
        return dict(fn(task))

    def _invoke_diagnostic(self, fn: Any, key: str, task: str) -> dict[str, Any]:
        if key == "disk":
            return dict(fn())
        if key == "system":
            return dict(fn())
        if key == "log":
            return dict(fn("System"))
        if key == "network":
            return dict(fn("127.0.0.1", "4"))
        if key == "process":
            return dict(fn())
        if key == "service":
            return dict(fn())
        if key == "why_running":
            target = self._extract_target(task)
            return dict(fn(target))
        return dict(fn())

    @staticmethod
    def _extract_target(task: str) -> str:
        """Extrait un target witr probable (nom de process, port, service)."""
        tokens = re.findall(r"[A-Za-z0-9_.\-:]{2,}", task)
        # Mots-clés witr + stopwords FR/EN courants à exclure du target
        excluded = {
            "pourquoi",
            "why",
            "running",
            "tourne",
            "sur",
            "le",
            "la",
            "les",
            "ce",
            "cette",
            "qui",
            "que",
            "est",
            "a",
            "en",
            "processus",
            "process",
            "service",
            "port",
            "occupe",
            "utilise",
            "utiliser",
            "est-ce",
            "demarre",
            "started",
            "is",
            "this",
            "ancestry",
            "quel",
            "quelle",
            "explique",
            "explain",
        }
        candidates = [t for t in tokens if t.lower() not in excluded]
        return candidates[0] if candidates else ""

    # ------------------------------------------------------------------
    # Formatage des résultats pour le prompt LLM
    # ------------------------------------------------------------------

    def _format_stdout(self, lines: list[str], r: dict[str, Any]) -> None:
        stdout = r.get("stdout", "")
        if stdout:
            lines.append(f"    {stdout[:MAX_STDOUT_LENGTH]}")
        data = r.get("data")
        if data is not None:
            lines.append(f"    {json.dumps(data, ensure_ascii=False)[:MAX_STDOUT_LENGTH]}")

    def _format_list_dir(self, lines: list[str], r: dict[str, Any]) -> None:
        entries = r.get("entries")
        if entries is None:
            return
        for e in entries[:MAX_ENTRIES]:
            lines.append(f"    {'D' if e['is_dir'] else 'F'} {e['name']}  ({e['size']} o)")
        if len(entries) > MAX_ENTRIES:
            lines.append(f"    ... et {len(entries) - MAX_ENTRIES} autres entrees")

    def _format_read_file(self, lines: list[str], r: dict[str, Any]) -> None:
        content = r.get("content")
        if content is not None:
            lines.append(f"    {content[:MAX_CONTENT_LENGTH]}")

    def _format_find_files(self, lines: list[str], r: dict[str, Any]) -> None:
        matches = r.get("matches")
        if matches is None:
            return
        for m in matches[:MAX_MATCHES]:
            lines.append(f"    {m}")
        if len(matches) > MAX_MATCHES:
            lines.append(f"    ... et {len(matches) - MAX_MATCHES} autres fichiers")

    def _format_error(self, lines: list[str], r: dict[str, Any]) -> None:
        error = r.get("error", "")
        if error:
            lines.append(f"    Erreur: {error}")

    def _format_result(self, key: str, r: dict[str, Any]) -> list[str]:
        lines = []
        status = "OK" if r.get("success") else "ECHEC"
        lines.append(f"  [{status}] {key}:")
        self._format_stdout(lines, r)
        self._format_list_dir(lines, r)
        self._format_read_file(lines, r)
        self._format_find_files(lines, r)
        self._format_error(lines, r)
        return lines

    def tool_results_to_prompt(self, results: dict[str, dict[str, Any]]) -> str:
        if not results:
            return ""
        lines = ["\n[Resultats diagnostics]", ""]
        for key, r in results.items():
            lines.extend(self._format_result(key, r))
        return "\n".join(lines)
