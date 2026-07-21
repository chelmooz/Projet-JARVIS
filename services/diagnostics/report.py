"""Report — Affichage coloré du rapport de diagnostic."""

from __future__ import annotations

from services.diagnostics.rules import Severity

# Codes ANSI pour le formatage terminal (foreground colors + reset)
_COLORS = {
    Severity.FAIL: "\033[91mFAIL\033[0m",
    Severity.WARN: "\033[93mWARN\033[0m",
    Severity.OK: "\033[92m OK \033[0m",
    Severity.INFO: "\033[94mINFO\033[0m",
}


def _color(severity: Severity) -> str:
    """Retourne le tag coloré ANSI correspondant à la sévérité."""
    return _COLORS.get(severity, f"\033[0m{severity.name}\033[0m")


def _infer_severity(rec: str) -> Severity:
    """Déduit la sévérité à partir du préfixe de la recommandation."""
    if rec.startswith("[FAIL]"):
        return Severity.FAIL
    if rec.startswith("[WARN]"):
        return Severity.WARN
    if rec.startswith("[OK]"):
        return Severity.OK
    return Severity.INFO


def print_report(recommendations: list[str], verdict: str) -> None:
    """Affiche le rapport de diagnostic avec des couleurs ANSI dans le terminal.

    Args:
        recommendations: Liste des chaînes de recommandations formatées.
        verdict: Chaîne de verdict global (ex: "OK", "WARNING (1 avertissement)").
    """
    for rec in recommendations:
        sev = _infer_severity(rec)
        tag = _color(sev)
        # Extraction robuste du message après le premier crochet fermant
        msg = rec.split("]", 1)[-1].strip()
        print(f"  [{tag}] {msg}")
    
    print(f"\n  Verdict : {verdict}")


__all__ = ["print_report"]
