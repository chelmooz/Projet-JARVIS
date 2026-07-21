"""Report — Affichage coloré du rapport de diagnostic."""
from services.diagnostics.rules import Severity


def _color(severity: Severity) -> str:
    return {
        Severity.FAIL: "\033[91mFAIL\033[0m",
        Severity.WARN: "\033[93mWARN\033[0m",
        Severity.OK: "\033[92m OK \033[0m",
        Severity.INFO: "\033[94mINFO\033[0m",
    }[severity]


def _infer_severity(rec: str) -> Severity:
    if rec.startswith("[FAIL]"):
        return Severity.FAIL
    if rec.startswith("[WARN]"):
        return Severity.WARN
    if rec.startswith("[OK]"):
        return Severity.OK
    return Severity.INFO


def print_report(recommendations: list[str], verdict: str):
    for rec in recommendations:
        sev = _infer_severity(rec)
        tag = _color(sev)
        msg = rec.split("]", 1)[1].strip() if "]" in rec else rec
        print(f"  [{tag}] {msg}")
    print(f"\n  Verdict : {verdict}")
