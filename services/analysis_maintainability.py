"""MaintainabilityAnalyzer — maintenabilité : complexité, duplication, branches, except nu."""

from __future__ import annotations

import ast
from typing import Iterator

from services.analysis_core import (
    _MAX_BRANCHES,
    _MAX_CYCLOMATIC,
    _MAX_DUPLICATE_LINES,
    _NAKED_EXCEPT,
    _node_name,
)
from services.analysis_report import AnalysisReport


class MaintainabilityAnalyzer:
    """Vérifie les règles de maintenabilité d'un fichier Python."""

    def check(self, report: AnalysisReport, tree: ast.AST, lines: list[str]) -> None:
        """Exécute toutes les vérifications de maintenabilité sur le fichier."""
        self._check_cyclomatic_complexity(report, tree)
        self._check_code_duplication(report, lines)
        self._check_too_many_branches(report, tree)
        self._check_naked_except(report, lines)

    def _walk_local(self, node: ast.AST) -> Iterator[ast.AST]:
        """Parcours local d'un nœud AST (n'entre pas dans les fonctions/classes imbriquées)."""
        yield node
        for child in ast.iter_child_nodes(node):
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield from self._walk_local(child)

    def _check_cyclomatic_complexity(self, report: AnalysisReport, tree: ast.AST) -> None:
        """Vérifie la complexité cyclomatique des fonctions (max _MAX_CYCLOMATIC)."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = 1
                for sub in self._walk_local(node):
                    if isinstance(sub, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler)):
                        complexity += 1
                    elif isinstance(sub, ast.BoolOp):
                        complexity += len(sub.values) - 1
                if complexity > _MAX_CYCLOMATIC:
                    report.add(
                        "maintainability",
                        "major",
                        node.lineno,
                        f"Complexité cyclomatique de {complexity} (max {_MAX_CYCLOMATIC}) — refactor recommandé",
                        f"Fonction '{_node_name(node)}' : complexité {complexity}",
                    )
                    report.penalize(4)

    def _check_code_duplication(self, report: AnalysisReport, lines: list[str]) -> None:
        """Détecte les blocs de code dupliqués (min _MAX_DUPLICATE_LINES lignes)."""
        seen: dict[tuple[str, ...], int] = {}
        i = 0
        while i < len(lines) - _MAX_DUPLICATE_LINES + 1:
            block = [lines[i + j].strip() for j in range(_MAX_DUPLICATE_LINES)]
            # Ignore les commentaires, docstrings, définitions de fonctions/classes, décorateurs.
            cleaned = [b for b in block if b and not b.startswith(("#", '"""', "'''", "def ", "class ", "@"))]
            if len(cleaned) >= _MAX_DUPLICATE_LINES - 1:
                key = tuple(cleaned)
                if key in seen:
                    prev = seen[key]
                    # Ne pas signaler si les blocs sont adjacents (tolérance).
                    if abs(i - prev) > _MAX_DUPLICATE_LINES:
                        report.add(
                            "maintainability",
                            "major",
                            i + 1,
                            f"Bloc dupliqué détecté (lignes {prev + 1}-{prev + len(key)}) — extraire en fonction",
                            lines[i][:80],
                        )
                        report.penalize(3)
                        i += _MAX_DUPLICATE_LINES
                        continue
                else:
                    seen[key] = i
            i += 1

    def _check_too_many_branches(self, report: AnalysisReport, tree: ast.AST) -> None:
        """Vérifie le nombre de branches conditionnelles par fonction (max _MAX_BRANCHES)."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                branches = sum(1 for sub_node in self._walk_local(node) if isinstance(sub_node, ast.If))
                if branches > _MAX_BRANCHES:
                    report.add(
                        "maintainability",
                        "major",
                        node.lineno,
                        f"Trop de branches conditionnelles ({branches}, max {_MAX_BRANCHES})",
                        f"Fonction '{_node_name(node)}' : {branches} if",
                    )
                    report.penalize(3)

    def _check_naked_except(self, report: AnalysisReport, lines: list[str]) -> None:
        """Détecte les `except:` nus (attrapent aussi KeyboardInterrupt/SystemExit)."""
        for i, line in enumerate(lines):
            if _NAKED_EXCEPT.search(line):
                report.add(
                    "maintainability",
                    "major",
                    i + 1,
                    "except: nu attrape aussi KeyboardInterrupt/SysExit — précisez le type",
                    "except:",
                )
                report.penalize(3)


__all__ = ["MaintainabilityAnalyzer"]
