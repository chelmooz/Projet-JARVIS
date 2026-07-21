"""StandardsAnalyzer + TestExistenceChecker — coding standards et présence de tests.

Fusionne la duplication I7 : `_check_testing` et `check_test_exists` partagent
désormais `_resolve_test_candidates` (services.analysis_core).
"""
import ast
import os
import re

from services.analysis_core import (
    _MAX_FILE_LINES,
    _MAX_FUNC_LINES,
    _MAX_NESTING,
    _MAX_PARAMS,
    _has_early_return,
    _max_nest_depth,
    _node_name,
    _resolve_test_candidates,
)
from services.analysis_report import AnalysisReport


class CodingStandardsAnalyzer:
    """Vérifie les règles Clean Code / coding standards d'un fichier Python."""

    def check(self, report: AnalysisReport, tree: ast.AST, lines: list[str]):
        self._check_file_length(report, lines)
        self._check_function_length(report, tree)
        self._check_too_many_params(report, tree)
        self._check_nesting(report, tree)
        self._check_naming(report, tree)
        self._check_docstrings(report, tree)
        self._check_srp(report, tree)
        self._check_comments_ratio(report, lines)
        self._check_else_usage(report, tree)

    def _check_file_length(self, report: AnalysisReport, lines):
        if len(lines) > _MAX_FILE_LINES:
            report.add("coding_standard", "major", len(lines),
                       f"Fichier trop long : {len(lines)} lignes (max {_MAX_FILE_LINES})")
            report.penalize(5)

    def _check_function_length(self, report: AnalysisReport, tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nlines = node.end_lineno - node.lineno + 1 if hasattr(node, "end_lineno") else 0
                if nlines > _MAX_FUNC_LINES:
                    report.add("coding_standard", "major", node.lineno,
                               f"Fonction '{_node_name(node)}' : {nlines} lignes (max {_MAX_FUNC_LINES}) — SRP/Clean Code")
                    report.penalize(5)

    def _check_too_many_params(self, report: AnalysisReport, tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                has_self = args.args and args.args[0].arg in ("self", "cls")
                total = len(args.args) + len(args.kwonlyargs) - (1 if has_self else 0)
                if total > _MAX_PARAMS:
                    report.add("coding_standard", "major", node.lineno,
                               f"Fonction '{_node_name(node)}' : {total} parametres (max {_MAX_PARAMS}) — Clean Code")
                    report.penalize(3)

    def _check_nesting(self, report: AnalysisReport, tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                max_depth = _max_nest_depth(node)
                if max_depth > _MAX_NESTING:
                    report.add("coding_standard", "major", node.lineno,
                               f"Fonction '{_node_name(node)}' : {max_depth} niveaux d'imbrication (max {_MAX_NESTING}) — KISS")
                    report.penalize(5)

    def _check_naming(self, report: AnalysisReport, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                self._check_variable_naming(report, node)
                continue
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and not re.match(r"^[a-z_][a-z0-9_]*$", node.name):
                report.add("coding_standard", "major", node.lineno,
                           f"Fonction '{node.name}' : doit etre en snake_case — Clean Code")
                report.penalize(2)

    def _check_variable_naming(self, report: AnalysisReport, node):
        if node.id.startswith("_"):
            return
        if re.match(r"^[a-z_][a-z0-9_]*$", node.id):
            return
        if node.id == node.id.upper():
            return
        report.add("coding_standard", "minor", node.lineno,
                   f"Variable '{node.id}' : doit etre en snake_case — Clean Code")
        report.penalize(1)

    def _check_docstrings(self, report: AnalysisReport, tree):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue
                docstring = ast.get_docstring(node)
                if not docstring:
                    report.add("coding_standard", "minor", node.lineno,
                               f"'{_node_name(node)}' : docstring manquante — Clean Code")
                    report.penalize(1)

    def _check_srp(self, report: AnalysisReport, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._flag_class_srp(report, node)
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._flag_function_srp(report, node)

    def _flag_class_srp(self, report: AnalysisReport, node):
        methods = [n for n in ast.walk(node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if len(methods) > 15:
            report.add("coding_standard", "major", node.lineno,
                       f"Classe '{node.name}' : {len(methods)} methodes — possible violation SRP")
            report.penalize(3)

    def _flag_function_srp(self, report: AnalysisReport, node):
        topics = self._distinct_call_topics(node)
        if len(topics) > 10:
            report.add("coding_standard", "minor", node.lineno,
                       f"Fonction '{_node_name(node)}' : {len(topics)} appels distincts — possible violation SRP")
            report.penalize(2)

    def _distinct_call_topics(self, node) -> set:
        topics = set()
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Attribute):
                topics.add(call.func.attr)
            elif isinstance(call.func, ast.Name):
                topics.add(call.func.id)
        return topics

    def _check_comments_ratio(self, report: AnalysisReport, lines):
        total = len(lines)
        if total == 0:
            return
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
        ratio = comment_lines / total
        if ratio > 0.3:
            report.add("coding_standard", "minor", 0,
                       f"Trop de commentaires : {comment_lines}/{total} lignes ({ratio:.0%}) — Clean Code")
            report.penalize(3)

    def _check_else_usage(self, report: AnalysisReport, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and node.orelse:
                inner = node.orelse[0] if node.orelse else None
                if isinstance(inner, ast.If):
                    continue
                if _has_early_return(node.body) and len(node.orelse) <= 3:
                    report.add("coding_standard", "minor", node.lineno,
                               "else superflu : early return possible — Clean Code")
                    report.penalize(1)


class TestExistenceChecker:
    """Vérifie la présence d'un fichier de test pour un module source."""

    def check(self, report: AnalysisReport, path: str):
        candidates = _resolve_test_candidates(path)
        found = [p for p in candidates if os.path.exists(p)]
        if not found:
            report.add("testing", "minor", 0,
                       f"Aucun fichier de test trouvé pour '{os.path.basename(path)}' — TDD", "")
            report.penalize(3)

    def resolve(self, source_path: str) -> dict:
        candidates = _resolve_test_candidates(source_path)
        found = [p for p in candidates if os.path.exists(p)]
        return {"source": source_path, "test_found": len(found) > 0, "test_paths": found}
