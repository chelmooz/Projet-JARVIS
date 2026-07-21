"""PerformanceAnalyzer — performance : boucles imbriquées, N+1, générateurs, appels répétés."""
import ast

from services.analysis_core import _MAX_NESTED_LOOPS, _get_call_name
from services.analysis_report import AnalysisReport


class PerformanceAnalyzer:
    """Vérifie les règles de performance d'un fichier Python."""

    def check(self, report: AnalysisReport, tree: ast.AST):
        self._check_nested_loops(report, tree)
        self._check_nplusone(report, tree)
        self._check_list_vs_generator(report, tree)
        self._check_repeated_calls_in_loop(report, tree)

    def _check_nested_loops(self, report: AnalysisReport, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._find_nested_loops(report, node, 0)

    def _find_nested_loops(self, report: AnalysisReport, node, depth):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
                if depth >= _MAX_NESTED_LOOPS:
                    report.add("performance", "major", child.lineno,
                               f"Boucle imbriquée niveau {depth + 1} — complexité O(n^{depth + 1}) potentielle",
                               ast.unparse(child)[:100])
                    report.penalize(3)
                self._find_nested_loops(report, child, depth + 1)
            elif not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._find_nested_loops(report, child, depth)

    def _check_nplusone(self, report: AnalysisReport, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                body_calls = 0
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        name = _get_call_name(sub)
                        if any(kw in name.lower() for kw in ("query", "get", "fetch", "filter", "execute")):
                            body_calls += 1
                if body_calls >= 2:
                    report.add("performance", "major", node.lineno,
                               f"N+1 query potentiel : {body_calls} appels DB dans une boucle",
                               ast.unparse(node)[:120])
                    report.penalize(5)

    def _check_list_vs_generator(self, report: AnalysisReport, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "list":
                    for arg in node.args:
                        if isinstance(arg, ast.ListComp):
                            report.add("performance", "minor", node.lineno,
                                       "list([...]) superflu : la liste est déjà une compréhension",
                                       ast.unparse(node)[:80])
                            report.penalize(1)

    def _check_repeated_calls_in_loop(self, report: AnalysisReport, tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                calls = {}
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        key = ast.unparse(sub.func)
                        calls[key] = calls.get(key, 0) + 1
                for fn, count in calls.items():
                    if count >= 3:
                        report.add("performance", "major", node.lineno,
                                   f"Appel répété à '{fn}' ({count}x) — hoisting possible hors de la boucle",
                                   f"{fn} appelé {count} fois")
                        report.penalize(3)
