"""Formatters de résultat — stratégies de normalisation de la sortie subprocess.

Distinction texte vs structurée (JSON) : un outil comme witr produit du
JSON natif (`--json`) qui ne doit pas être tronqué en texte brut. Le
formatter est choisi par ``output_format`` dans la config de l'outil.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

_MAX_STDOUT = 2000
_MAX_STDERR = 500
_MAX_ERROR = 200

# Pattern de la liste numérotée du mode interactif witr (leçon T5) :
# plusieurs cibles matchent → sortie texte brut "[1] …".."[n] …", pas de JSON.
_NUMBERED_LIST_RE = re.compile(r"^\s*\[\d+\]\s*(.+)$")


class TextResultFormatter:
    """Comportement historique : stdout/stderr tronqués en texte brut."""

    def format(
        self, tool_name: str, proc: subprocess.CompletedProcess[str]
    ) -> dict[str, Any]:
        """Normalise un subprocess réussi en dict de résultat texte."""
        return {
            "success": proc.returncode == 0,
            "tool": tool_name,
            "stdout": proc.stdout.strip()[:_MAX_STDOUT],
            "stderr": proc.stderr.strip()[:_MAX_STDERR],
            "returncode": proc.returncode,
        }


class JsonResultFormatter:
    """Parse le stdout en JSON : ne tronque pas la structure.

    Retombe proprement en erreur lisible si le JSON est invalide
    (jamais d'exception propagée à l'appelant).
    """

    def format(
        self, tool_name: str, proc: subprocess.CompletedProcess[str]
    ) -> dict[str, Any]:
        """Normalise un subprocess en dict de résultat JSON."""
        try:
            data: Any = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            candidates = self._detect_ambiguous_targets(proc.stdout)
            if candidates:
                return {
                    "success": False,
                    "tool": tool_name,
                    "error": (
                        f"Cible ambiguë : {len(candidates)} processus correspondent "
                        f"(liste numérotée witr)"
                    ),
                    "data": {"ambiguous": True, "candidates": candidates},
                    "returncode": proc.returncode,
                }
            return {
                "success": False,
                "tool": tool_name,
                "error": f"Sortie JSON invalide: {str(e)[:_MAX_ERROR]}",
                "stdout": proc.stdout.strip()[:_MAX_STDOUT],
                "returncode": proc.returncode,
            }
        return {
            "success": proc.returncode == 0,
            "tool": tool_name,
            "data": data,
            "returncode": proc.returncode,
        }

    @staticmethod
    def _detect_ambiguous_targets(stdout: str) -> list[str]:
        """Détecte la liste numérotée du mode interactif witr (≥ 2 entrées).

        Retourne la liste des cibles candidates (texte après ``[n]``) ou une
        liste vide si le pattern ne correspond pas — l'appelant retombe alors
        sur l'erreur JSON générique.
        """
        candidates = [
            m.group(1).strip()
            for line in stdout.splitlines()
            if line.strip()
            for m in [_NUMBERED_LIST_RE.match(line)]
            if m
        ]
        return candidates if len(candidates) >= 2 else []


def get_formatter(output_format: str) -> TextResultFormatter | JsonResultFormatter:
    """Factory : retourne le formatter adapté au format de sortie de l'outil."""
    if output_format == "json":
        return JsonResultFormatter()
    return TextResultFormatter()


__all__ = [
    "TextResultFormatter",
    "JsonResultFormatter",
    "get_formatter",
    "_MAX_STDOUT",
    "_MAX_STDERR",
    "_MAX_ERROR",
]
