"""AnalysisReport — rapport unifié des analyseurs statiques.

Classe standalone (sans dépendance d'analyse) : dictionnaire enrichi
avec findings classés par criticité (critical/major/minor).
"""

from __future__ import annotations

from typing import Any


class AnalysisReport(dict):
    """Rapport unifié avec findings classés par criticité (critical/major/minor)."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self["path"] = path
        self["findings"]: list[dict[str, Any]] = []
        self["score"] = 100
        self["summary"]: dict[str, int] = {}

    def add(
        self,
        category: str,
        severity: str,
        line: int,
        msg: str,
        snippet: str = "",
    ) -> None:
        """Ajoute un finding au rapport (category, severity, line, message, snippet)."""
        self["findings"].append({
            "category": category,
            "severity": severity,
            "line": line,
            "message": msg,
            "snippet": snippet,
        })

    @property
    def total(self) -> int:
        """Nombre total de findings."""
        return len(self["findings"])

    def penalize(self, n: int) -> None:
        """Pénalise le score de n points (minimum 0)."""
        self["score"] = max(0, self["score"] - n)

    def finalize(self) -> AnalysisReport:
        """Finalise le rapport : calcule le summary et retourne self."""
        findings = self["findings"]
        self["summary"] = {
            "total": len(findings),
            "critical": sum(1 for x in findings if x["severity"] == "critical"),
            "major": sum(1 for x in findings if x["severity"] == "major"),
            "minor": sum(1 for x in findings if x["severity"] == "minor"),
        }
        if not findings:
            self["score"] = 100
        return self

    @property
    def violations(self) -> list[dict[str, Any]]:
        """Alias de `findings` (liste des violations détectées)."""
        return self["findings"]


__all__ = ["AnalysisReport"]
