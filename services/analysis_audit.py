"""QualityAuditor — audit complet du projet : 4 axes pondérés.

Importe `Analyzer` paresseusement (dans `__init__`) pour éviter l'import
circulaire avec services.analysis (qui réexporte QualityAuditor).

Conforme au skill clean-code : les conditionnelles complexes sont encapsulées
dans des fonctions nommées (3.J), pas de chaînes if/elif dupliquées (DRY),
fonctions courtes à un niveau d'abstraction (3.B).
"""

from __future__ import annotations

import ast
import contextlib
import os
import subprocess
import sys
from typing import Any

from services.analysis_core import (
    _PROJECT_ROOT,
    _SOURCE_DIRS,
    _TEST_DIR,
    _WEIGHTS,
    _count_lines,
    _py_files,
)


def _source_py_files() -> list[str]:
    """Tous les fichiers Python source (dédoublonnés, triés).

    Réutilise `analysis_core._py_files` : évite le re-parcours maison
    présent jadis dans `_find_dead_files` (DRY).
    """
    return sorted(set(f for d in _SOURCE_DIRS for f in _py_files(d)))


_IMPORT_PREFIXES = ("services.", "controllers.", "agents.", "config.", "models.", "graph.")
_PYTEST_TOKENS = {"passed": "passed", "failed": "failed", "errors": "errors"}


class QualityAuditor:
    """Audit complet du projet : 4 axes pondérés."""

    def __init__(self) -> None:
        from services.analysis import Analyzer

        self._analyzer = Analyzer()

    def audit(self) -> dict[str, Any]:
        """Exécute l'audit complet et retourne le rapport agrégé."""
        report: dict[str, Any] = {}
        self._audit_code_quality(report)
        self._audit_tests(report)
        self._audit_structure(report)
        self._audit_documentation(report)
        return self._finalize(report)

    def _finalize(self, report: dict[str, Any]) -> dict[str, Any]:
        """Calcule le score global pondéré."""
        total = 0.0
        weight_sum = 0.0
        for cat, w in _WEIGHTS.items():
            pct = report.get(cat, {}).get("pct", 0)
            total += pct * w
            weight_sum += w
        report["overall"] = round(total / weight_sum, 1) if weight_sum else 0
        return report

    def _set_score(
        self,
        report: dict[str, Any],
        category: str,
        score: float,
        max_score: float,
        details: dict[str, Any],
    ) -> None:
        """Enregistre le score d'une catégorie dans le rapport."""
        pct = round((score / max_score * 100) if max_score else 0, 1)
        report[category] = {"score": score, "max": max_score, "pct": pct, "details": details}

    # ------------------------------------------------------------------
    # Code Quality
    # ------------------------------------------------------------------

    def _audit_code_quality(self, report: dict[str, Any]) -> None:
        """Audit de la qualité du code (score moyen, findings, erreurs critiques)."""
        source_files = _source_py_files()
        scores: list[float] = []
        all_findings = 0
        total_lines = 0
        critical_counts = {"syntax": 0, "io": 0}

        for fp in source_files:
            total_lines += _count_lines(fp)
            r = self._analyzer.analyze_file(fp)
            scores.append(r["score"])
            all_findings += r.total
            self._count_critical_findings(r, critical_counts)

        avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        self._set_score(report, "code_quality", avg_score, 100, {
            "files_analyzed": len(source_files),
            "total_lines": total_lines,
            "total_findings": all_findings,
            "avg_score": avg_score,
            "syntax_errors": critical_counts["syntax"],
            "io_errors": critical_counts["io"],
        })

    def _count_critical_findings(self, report: Any, critical_counts: dict[str, int]) -> None:
        """Compte tous les findings critiques (pas seulement le premier)."""
        if report.total == 0 or not report.get("findings"):
            return
        for finding in report["findings"]:
            if finding.get("severity") == "critical" and finding.get("category") in critical_counts:
                critical_counts[finding["category"]] += 1

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def _audit_tests(self, report: dict[str, Any]) -> None:
        """Audit de la couverture de tests (existence + exécution pytest)."""
        if not os.path.isdir(_TEST_DIR):
            self._set_score(report, "tests", 0, 100, {"error": "Répertoire tests/ introuvable"})
            return

        source_files = _source_py_files()
        covered = sum(1 for sf in source_files if self._analyzer.check_test_exists(sf)["test_found"])
        coverage_pct = round(covered / len(source_files) * 100, 1) if source_files else 0

        pytest_result = self._run_pytest()
        composite = round(pytest_result.get("pass_pct", 0) * 0.5 + coverage_pct * 0.5, 1)
        details: dict[str, Any] = {
            "test_files": len(_py_files(_TEST_DIR)),
            "total_tests": pytest_result.get("total", 0),
            "passed": pytest_result.get("passed", 0),
            "failed": pytest_result.get("failed", 0),
            "errors": pytest_result.get("errors", 0),
            "pass_rate": pytest_result.get("pass_pct", 0),
            "source_files_total": len(source_files),
            "source_files_with_tests": covered,
            "test_existence_coverage": coverage_pct,
        }
        if pytest_result.get("error"):
            details["pytest_error"] = pytest_result["error"]
        self._set_score(report, "tests", composite, 100, details)

    def _parse_pytest_counts(self, output: str) -> dict[str, int]:
        """Parse la sortie de pytest pour extraire les compteurs."""
        counts = {"passed": 0, "failed": 0, "errors": 0}
        for line in output.splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            for i, token in enumerate(parts):
                field = _PYTEST_TOKENS.get(token)
                if field is not None and i > 0:
                    self._store_count(counts, parts, i, field)
        return counts

    def _store_count(self, counts: dict[str, int], parts: list[str], index: int, field: str) -> None:
        """Stocke un compteur parsé (ignore les erreurs de conversion)."""
        with contextlib.suppress(ValueError):
            counts[field] = int(parts[index - 1])

    def _run_pytest(self) -> dict[str, Any]:
        """Exécute pytest et retourne les résultats agrégés."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(_TEST_DIR), "--tb=no", "-q", "--no-header", "-o", "addopts="],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=_PROJECT_ROOT,
            )
            counts = self._parse_pytest_counts(result.stdout + result.stderr)
            total = sum(counts.values())
            pass_pct = round(counts["passed"] / total * 100, 1) if total else 0
            return {
                "total": total,
                "passed": counts["passed"],
                "failed": counts["failed"],
                "errors": counts["errors"],
                "pass_pct": pass_pct,
            }
        except (subprocess.TimeoutExpired, OSError) as e:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "pass_pct": 0,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Structure
    # ------------------------------------------------------------------

    def _py_module_names(self, subdir: str) -> list[str]:
        """Liste les modules Python d'un sous-répertoire (hors __init__)."""
        full = os.path.join(_PROJECT_ROOT, subdir)
        if not os.path.isdir(full):
            return []
        return [f for f in os.listdir(full) if f.endswith(".py") and not f.startswith("__")]

    def _audit_structure(self, report: dict[str, Any]) -> None:
        """Audit de la structure du projet (fichiers requis, imports, dead code)."""
        route_files = self._py_module_names("controllers/routes")
        service_files = self._py_module_names("services")

        all_source = list(_source_py_files())
        if os.path.isdir(_TEST_DIR):
            all_source.extend(_py_files(_TEST_DIR))

        import_issues = self._check_imports(all_source)
        dead_files = self._find_dead_files()
        has_project_files = (
            os.path.exists(os.path.join(_PROJECT_ROOT, "pyproject.toml"))
            and os.path.isdir(os.path.join(_PROJECT_ROOT, "config"))
        )

        # Checks structurés (éviter les listes parallèles fragiles).
        checks = [
            ("controllers/router.py manquant", os.path.exists(os.path.join(_PROJECT_ROOT, "controllers", "router.py"))),
            ("Aucun fichier de route dans controllers/routes/", bool(route_files)),
            ("Aucun service dans services/", bool(service_files)),
            ("Répertoire tests/ manquant", os.path.isdir(_TEST_DIR)),
            (f"{len(import_issues)} imports invalides ou cycliques", not import_issues),
            (f"{len(dead_files)} fichiers orphelins potentiels", not dead_files),
            ("pyproject.toml ou config/ manquant", has_project_files),
        ]

        issues = [label for label, passed in checks if not passed]
        ok_count = sum(1 for _, passed in checks if passed)
        total_checks = len(checks)
        score = round(ok_count / total_checks * 100, 1) if total_checks else 0
        self._set_score(report, "structure", score, 100, {
            "checks_passed": ok_count,
            "checks_total": total_checks,
            "route_files": len(route_files),
            "service_files": len(service_files),
            "issues": issues,
            "dead_files": dead_files,
            "import_issues": import_issues[:10] if import_issues else [],
        })

    def _check_imports(self, py_files: list[str]) -> list[str]:
        """Vérifie les imports (existence statique, pas d'exécution de code)."""
        import_issues: list[str] = []
        checked: set[tuple[str, str]] = set()
        for fp in py_files:
            self._scan_file_imports(fp, import_issues, checked)
        return import_issues

    def _scan_file_imports(
        self,
        fp: str,
        import_issues: list[str],
        checked: set[tuple[str, str]],
    ) -> None:
        """Scanne les imports d'un fichier et vérifie leur existence."""
        try:
            with open(fp, encoding="utf-8", errors="replace") as f:
                tree = ast.parse(f.read(), filename=fp)
            for node in ast.walk(tree):
                self._register_node_import(fp, node, import_issues, checked)
        except (SyntaxError, OSError):
            import_issues.append(f"{fp}: impossible de parser")

    def _register_node_import(
        self,
        fp: str,
        node: ast.AST,
        import_issues: list[str],
        checked: set[tuple[str, str]],
    ) -> None:
        """Enregistre un nœud d'import pour vérification."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                self._register_import(fp, alias.name, f"import {alias.name} échoué", import_issues, checked)
        elif isinstance(node, ast.ImportFrom) and (node.level is None or node.level == 0):
            self._register_import(fp, node.module or "", f"from {node.module} import ... échoué", import_issues, checked)

    def _register_import(
        self,
        fp: str,
        mod: str,
        label: str,
        import_issues: list[str],
        checked: set[tuple[str, str]],
    ) -> None:
        """Vérifie l'existence d'un module (statique, pas d'exécution)."""
        if not mod.startswith(_IMPORT_PREFIXES):
            return
        key = (fp, mod)
        if key in checked:
            return
        checked.add(key)
        # Vérification statique : on ne fait PAS __import__(mod) (effets de bord).
        # On vérifie si le module existe dans sys.modules ou si le fichier existe.
        if mod not in sys.modules:
            # Essayer de trouver le fichier correspondant.
            parts = mod.split(".")
            potential_paths = [
                os.path.join(_PROJECT_ROOT, *parts) + ".py",
                os.path.join(_PROJECT_ROOT, *parts, "__init__.py"),
            ]
            if not any(os.path.exists(p) for p in potential_paths):
                import_issues.append(f"{fp}: {label}")

    def _find_dead_files(self) -> list[str]:
        """Trouve les fichiers source non importés (dead code)."""
        py_files = _source_py_files()
        # Une seule passe : lire tous les fichiers et construire un index de contenu.
        file_contents: dict[str, str] = {}
        all_content_parts: list[str] = []
        for fp in py_files:
            try:
                with open(fp, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                file_contents[fp] = text
                all_content_parts.append(text)
            except OSError:
                pass
        all_content = "\n".join(all_content_parts)

        dead: list[str] = []
        for fp, content in file_contents.items():
            basename = os.path.basename(fp)
            if basename == "__init__.py":
                continue
            rel = os.path.relpath(fp, _PROJECT_ROOT)
            if rel.startswith("scripts"):
                continue
            first_lines = content[:200]
            if 'if __name__ == "__main__"' in first_lines:
                continue
            mod_name = basename[:-3]
            refs = (
                f"import {mod_name}" in all_content
                or f"from {mod_name} " in all_content
                or f"from .{mod_name} " in all_content
                or f".{mod_name}" in all_content
            )
            if not refs:
                dead.append(fp)
        return dead

    # ------------------------------------------------------------------
    # Documentation
    # ------------------------------------------------------------------

    def _audit_documentation(self, report: dict[str, Any]) -> None:
        """Audit de la documentation (présence fichiers + docstrings)."""
        doc_items = self._audit_doc_presence()
        docstring_pct = self._audit_docstring_coverage()
        max_tokens = len(doc_items)
        tokens = sum(1 for _, state in doc_items if state == "present")
        score = round(tokens / max_tokens * 100, 1) if max_tokens else 0
        score = round(score * 0.6 + docstring_pct * 0.4, 1)
        self._set_score(report, "documentation", score, 100, {
            "files_present": doc_items,
            "docstring_coverage_pct": docstring_pct,
            "files_with_docstrings": sum(1 for _, s in doc_items if s == "present"),
            "total_source_files": len(_source_py_files()),
        })

    def _audit_doc_presence(self) -> list[tuple[str, str]]:
        """Présence des fichiers de documentation projet (responsabilité unique)."""
        items: list[tuple[str, str]] = []
        for fname in ("README.md", "CHANGELOG.md", "LICENSE", "CONTRIBUTING.md"):
            present = os.path.exists(os.path.join(_PROJECT_ROOT, fname))
            items.append((fname, "present" if present else "manquant"))
        has_glossary = os.path.exists(os.path.join(_PROJECT_ROOT, "docs", "glossaire.md"))
        items.append(("docs/glossaire.md", "present" if has_glossary else "manquant"))
        return items

    def _audit_docstring_coverage(self) -> float:
        """Pourcentage de fichiers source possédant au moins une docstring."""
        docstring_files = 0
        total_source = 0
        for fp in _source_py_files():
            total_source += 1
            if self._has_docstring(fp):
                docstring_files += 1
        return round(docstring_files / total_source * 100, 1) if total_source else 0.0

    def _has_docstring(self, fp: str) -> bool:
        """Vérifie si un fichier possède au moins une docstring (module, classe, fonction)."""
        try:
            with open(fp, encoding="utf-8", errors="replace") as f:
                tree = ast.parse(f.read(), filename=fp)
        except (SyntaxError, OSError):
            return False
        if ast.get_docstring(tree) is not None:
            return True
        nodes = (
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        return any(ast.get_docstring(n) is not None for n in nodes)


__all__ = ["QualityAuditor"]
