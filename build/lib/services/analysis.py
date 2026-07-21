"""Analysis — facade d'analyse statique unifiée (sécurité, perf, maintenabilité, standards).

Les responsabilités sont déléguées à des analyseurs dédiés :
- SecurityAnalyzer, PerformanceAnalyzer, MaintainabilityAnalyzer,
  CodingStandardsAnalyzer, TestExistenceChecker (services.analysis_*).
- QualityAuditor + AnalysisReport : services.analysis_audit / analysis_report.

L'API publique est préservée : analyze_file, analyze_project,
generate_global_report, check_test_exists, ainsi que l'alias review_file.
"""
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

    review_file = None  # backward compat: assigné après la définition de classe

    def __init__(self):
        self._security = SecurityAnalyzer()
        self._performance = PerformanceAnalyzer()
        self._maintainability = MaintainabilityAnalyzer()
        self._standards = CodingStandardsAnalyzer()
        self._tests = TestExistenceChecker()

    def analyze_file(self, path: str) -> AnalysisReport:
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
        return self._tests.resolve(source_path)

    def analyze_project(self, root: str) -> list[AnalysisReport]:
        reports = []
        for path in _py_files(root)[:_MAX_PROJECT_FILES]:
            if not os.path.basename(path).startswith("__"):
                reports.append(self.analyze_file(path))
        return reports

    def generate_global_report(self, root: str = None) -> dict:
        t0 = time.perf_counter()
        target = root or os.getcwd()
        reports = self.analyze_project(target)
        total_violations = sum(r.total for r in reports)
        avg_score = sum(r["score"] for r in reports) / len(reports) if reports else 0
        tests_ok = sum(1 for r in reports if self.check_test_exists(r["path"])["test_found"])
        elapsed = time.perf_counter() - t0
        return {
            "project": target,
            "files_analyzed": len(reports),
            "total_findings": total_violations,
            "average_score": round(avg_score, 1),
            "files_with_tests": tests_ok,
            "coverage_pct": round(tests_ok / len(reports) * 100, 1) if reports else 0,
            "elapsed_s": round(elapsed, 3),
            "reports": [dict(r) for r in reports],
        }


Analyzer.review_file = Analyzer.analyze_file  # backward compat alias
