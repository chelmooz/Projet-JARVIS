"""Toolbox — Boîte à outils pour les agents JARVIS.

Chaque agent peut invoquer :
  - des diagnostics externes (smartctl, Sysinternals)
  - des opérations fichiers (list_dir, read_file, find_files)
Les résultats sont formatés pour être injectés dans le prompt LLM.
"""
import os
import re

from config.paths import ROOT
from services.diagnostic_ext import DiagnosticExtService
from services.file_system import FileSystemService

MAX_STDOUT_LENGTH = 300
MAX_CONTENT_LENGTH = 500
MAX_MATCHES = 30
MAX_ENTRIES = 50
FALLBACK_DIR = ROOT

class Toolbox:
    """Gère les triggers, l'exécution et le formatage des résultats."""

    def __init__(self, diagnostic_service: DiagnosticExtService | None = None,
                 file_service: FileSystemService | None = None):
        self._diagnostic = diagnostic_service or DiagnosticExtService()
        self._file_system = file_service or FileSystemService()

        # ------------------------------------------------------------------
        # Triggers diagnostics (nécessitent consentement)
        # ------------------------------------------------------------------
        self._diagnostic_triggers = [
            (["disque", "disk", "smart", "hdd", "ssd", "stockage"],
             "disk", lambda _: self._diagnostic.run_smartctl()),
            (["info", "systeme", "system", "configuration"],
             "system", lambda _: self._diagnostic.run_psinfo()),
            (["log", "journal", "evenement", "event"],
             "log", lambda _: self._diagnostic.run_psloglist("System")),
            (["handle", "processus", "process", "fichier ouvert"],
             "process", lambda _: self._diagnostic.run_handle()),
            (["ping", "latence", "connectivite", "connectivity", "reseau", "network"],
             "network", lambda _: self._diagnostic.run_psping("127.0.0.1", "4")),
            (["service", "windows", "demarrage", "startup"],
             "service", lambda _: self._diagnostic.run_psservice()),
        ]

        # ------------------------------------------------------------------
        # Triggers fichiers (toujours actifs)
        # ------------------------------------------------------------------
        self._file_triggers = [
            (["liste", "dossier", "ls", "dir", "repertoire", "contenu du dossier"],
             "ls", lambda t: self._file_system.list_dir(self._extract_path(t))),
            (["cat", "ouvre", "read", "lecture", "lit", "fichier", "contenu du fichier", "texte"],
             "read", lambda t: self._file_system.read_file(self._extract_path(t))),
            (["cherche", "trouve", "find", "grep", "recherche"],
             "find", lambda t: self._file_system.find_files(self._extract_pattern(t))),
        ]

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
        path = m.group(0).rstrip('.,;:!?\'" ')
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
        lines = [
            "Outils disponibles :",
            "  - disk    : SMART disk health (smartctl)",
            "  - system  : system information (PsInfo)",
            "  - log     : Windows Event Log (psloglist)",
            "  - process : open file handles (handle)",
            "  - network : ping & latency (psping)",
            "  - service : service status (PsService)",
        ]
        if self._file_system.list_authorized():
            lines.extend([
                "  - ls      : lister un dossier autorise",
                "  - read    : lire un fichier texte (max 10 Ko)",
                "  - find    : chercher fichiers par pattern glob",
            ])
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Exécution automatique : matche les mots-clés de la tâche
    # ------------------------------------------------------------------

    def auto_execute(self, task: str) -> dict[str, dict]:
        results = {}
        lower = task.lower()
        for keywords, key, fn in self._diagnostic_triggers + self._file_triggers:
            if any(kw in lower for kw in keywords):
                try:
                    results[key] = fn(task)
                except Exception as e:
                    results[key] = {"success": False, "tool": key, "error": str(e)}
        return results

    # ------------------------------------------------------------------
    # Formatage des résultats pour le prompt LLM
    # ------------------------------------------------------------------

    def _format_stdout(self, lines: list[str], r: dict):
        stdout = r.get("stdout", "")
        if stdout:
            lines.append(f"    {stdout[:MAX_STDOUT_LENGTH]}")

    def _format_list_dir(self, lines: list[str], r: dict):
        entries = r.get("entries")
        if entries is None:
            return
        for e in entries[:MAX_ENTRIES]:
            lines.append(f"    {'D' if e['is_dir'] else 'F'} {e['name']}  ({e['size']} o)")
        if len(entries) > MAX_ENTRIES:
            lines.append(f"    ... et {len(entries)-MAX_ENTRIES} autres entrees")

    def _format_read_file(self, lines: list[str], r: dict):
        content = r.get("content")
        if content is not None:
            lines.append(f"    {content[:MAX_CONTENT_LENGTH]}")

    def _format_find_files(self, lines: list[str], r: dict):
        matches = r.get("matches")
        if matches is None:
            return
        for m in matches[:MAX_MATCHES]:
            lines.append(f"    {m}")
        if len(matches) > MAX_MATCHES:
            lines.append(f"    ... et {len(matches)-MAX_MATCHES} autres fichiers")

    def _format_error(self, lines: list[str], r: dict):
        error = r.get("error", "")
        if error:
            lines.append(f"    Erreur: {error}")

    def _format_result(self, key: str, r: dict) -> list[str]:
        lines = []
        status = "OK" if r.get("success") else "ECHEC"
        lines.append(f"  [{status}] {key}:")
        self._format_stdout(lines, r)
        self._format_list_dir(lines, r)
        self._format_read_file(lines, r)
        self._format_find_files(lines, r)
        self._format_error(lines, r)
        return lines

    def tool_results_to_prompt(self, results: dict[str, dict]) -> str:
        if not results:
            return ""
        lines = ["\n[Resultats diagnostics]", ""]
        for key, r in results.items():
            lines.extend(self._format_result(key, r))
        return "\n".join(lines)
