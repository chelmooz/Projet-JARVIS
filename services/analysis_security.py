"""SecurityAnalyzer — sécurité : secrets, appels dangereux, path traversal, SQLi, XSS."""
import ast

from services.analysis_core import (
    _EVAL_USAGE,
    _PATH_TRAVERSAL,
    _PICKLE_USAGE,
    _SECRET_PATTERNS,
    _XSS_RISK,
    _get_call_name,
)
from services.analysis_report import AnalysisReport


class SecurityAnalyzer:
    """Vérifie les règles de sécurité d'un fichier Python."""

    def check(self, report: AnalysisReport, code: str, tree):
        self._check_hardcoded_secrets(report, code)
        self._check_dangerous_calls(report, code)
        self._check_path_traversal(report, code)
        self._check_sql_injection(report, tree)
        self._check_xss(report, code)

    def _check_hardcoded_secrets(self, report: AnalysisReport, code: str):
        lines = code.splitlines()
        for pattern, kind in _SECRET_PATTERNS:
            for m in pattern.finditer(code):
                line = code[:m.start()].count("\n") + 1
                if line <= len(lines) and lines[line - 1].strip().startswith("#"):
                    continue
                snippet = m.group()[:80]
                report.add("security", "critical", line,
                           f"Secret {kind} détecté dans le code", snippet)
                report.penalize(10)

    def _check_dangerous_calls(self, report: AnalysisReport, code: str):
        lines = code.splitlines()
        for m in _EVAL_USAGE.finditer(code):
            line = code[:m.start()].count("\n") + 1
            keyword = m.group(1)
            if keyword == "__import__" and self._is_safe_import_check(lines, line):
                continue
            report.add("security", "critical", line,
                       f"Appel dangereux '{m.group().strip()}' — risque d'exécution de code arbitraire",
                       m.group().strip())
            report.penalize(8)
        for m in _PICKLE_USAGE.finditer(code):
            line = code[:m.start()].count("\n") + 1
            report.add("security", "major", line,
                       f"Utilisation de '{m.group().strip()}' — risque de désérialisation non sécurisée",
                       m.group().strip())
            report.penalize(5)

    @staticmethod
    def _is_safe_import_check(lines: list[str], line: int, window: int = 3) -> bool:
        """True si l'appel __import__ à `line` est encadré par un
        try/except ImportError dans les `window` lignes voisines — pattern de
        validation de résolvabilité d'import, pas d'exécution de code arbitraire.
        """
        start = max(0, line - 1 - window)
        end = min(len(lines), line + window)
        context = "\n".join(lines[start:end])
        return "except ImportError" in context and "try" in context

    def _check_path_traversal(self, report: AnalysisReport, code: str):
        for m in _PATH_TRAVERSAL.finditer(code):
            line = code[:m.start()].count("\n") + 1
            report.add("security", "major", line,
                       "Path traversal potentiel : entrée utilisateur dans une opération fichier",
                       m.group()[:100])
            report.penalize(5)

    def _check_sql_injection(self, report: AnalysisReport, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn_name = _get_call_name(node)
                if fn_name in ("execute", "executemany", "raw_input"):
                    for arg in node.args:
                        if isinstance(arg, ast.JoinedStr):
                            report.add("security", "critical", node.lineno,
                                       "SQL injection possible : f-string dans execute()",
                                       ast.unparse(node)[:100])
                            report.penalize(10)
                        elif isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):
                            report.add("security", "critical", node.lineno,
                                       "SQL injection possible : %% dans execute()",
                                       ast.unparse(node)[:100])
                            report.penalize(10)

    def _check_xss(self, report: AnalysisReport, code: str):
        for m in _XSS_RISK.finditer(code):
            line = code[:m.start()].count("\n") + 1
            report.add("security", "major", line,
                       "XSS potentielle : injection directe dans le DOM/HTML sans échappement",
                       m.group()[:100])
            report.penalize(5)
