"""Analysis — facade d'analyse statique unifiée (sécurité, perf, maintenabilité, standards).

Les responsabilités sont déléguées à des analyseurs dédiés :
- SecurityAnalyzer, PerformanceAnalyzer, MaintainabilityAnalyzer,
  CodingStandardsAnalyzer, TestExistenceChecker (services.analysis_*).
- QualityAuditor + AnalysisReport : services.analysis_audit / analysis_report.

L'API publique est préservée : analyze_file, analyze_project,
generate_global_report, check_test_exists, ainsi que l'alias review_file.
"""

from __future__ import annotations

import ast
import os
import time

from services import analysis_audit
from services.analysis_core import _MAX_PROJECT_FILES, _py_files
from services.analysis_maintainability import MaintainabilityAnalyzer
from services.analysis_performance import PerformanceAnalyzer
from services.analysis_report import AnalysisReport
from services.analysis_security import SecurityAnalyzer
from services.analysis_standards import CodingStandardsAnalyzer, TestExistenceChecker

# Réexport pour la compatibilité (routes/quality_audit.py importe QualityAuditor depuis ici).
QualityAuditor = analysis_audit.QualityAuditor


class Analyzer:
    """Analyseur statique unifié : délègue aux analyseurs par responsabilité."""

    def __init__(self) -> None:
        self._security = SecurityAnalyzer()
        self._performance = PerformanceAnalyzer()
        self._maintainability = MaintainabilityAnalyzer()
        self._standards = CodingStandardsAnalyzer()
        self._tests = TestExistenceChecker()

    def analyze_file(self, path: str) -> AnalysisReport:
        """Analyse un fichier Python et retourne un rapport d'analyse."""
        report = AnalysisReport(path)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                code = f.read()
        except OSError as e:
            report.add("io", "critical", 0, f"Impossible de lire le fichier : {e}")
            report.penalize(50)
            return report.finalize()
        try:
            tree = ast.parse(code, filename=path)
        except SyntaxError as e:
            report.add("syntax", "critical", e.lineno or 0, f"Erreur de syntaxe : {e.msg}")
            report.penalize(50)
            return report.finalize()
        lines = code.splitlines()
        self._security.check(report, code, tree)
        self._performance.check(report, tree)
        self._maintainability.check(report, tree, lines)
        self._standards.check(report, tree, lines)
        self._tests.check(report, path)
        return report.finalize()

    def check_test_exists(self, source_path: str) -> dict:
        """Vérifie si des tests existent pour le fichier source donné."""
        return self._tests.resolve(source_path)

    def analyze_project(self, root: str) -> list[AnalysisReport]:
        """Analyse tous les fichiers Python d'un projet (borné à _MAX_PROJECT_FILES)."""
        reports = []
        for path in _py_files(root)[:_MAX_PROJECT_FILES]:
            if not os.path.basename(path).startswith("__"):
                reports.append(self.analyze_file(path))
        return reports

    def generate_global_report(self, root: str | None = None) -> dict:
        """Génère un rapport global sur un projet (métriques agrégées)."""
        t0 = time.perf_counter()
        target = root or os.getcwd()
        reports = self.analyze_project(target)
        if not reports:
            return {
                "project": target,
                "files_analyzed": 0,
                "total_findings": 0,
                "average_score": 0.0,
                "files_with_tests": 0,
                "coverage_pct": 0.0,
                "elapsed_s": 0.0,
                "reports": [],
            }
        total_violations = sum(r.total for r in reports)
        avg_score = sum(r["score"] for r in reports) / len(reports)
        # Calcul unique des fichiers avec tests (évite le double appel check_test_exists).
        files_with_tests = 0
        for r in reports:
            if self.check_test_exists(r["path"])["test_found"]:
                files_with_tests += 1
        elapsed = time.perf_counter() - t0
        return {
            "project": target,
            "files_analyzed": len(reports),
            "total_findings": total_violations,
            "average_score": round(avg_score, 1),
            "files_with_tests": files_with_tests,
            "coverage_pct": round(files_with_tests / len(reports) * 100, 1),
            "elapsed_s": round(elapsed, 3),
            "reports": [dict(r) for r in reports],
        }

    # Alias backward-compat : review_file = analyze_file (même signature, même comportement).
    review_file = analyze_file


__all__ = ["Analyzer", "QualityAuditor"]
