from __future__ import annotations

from services.analysis_report import AnalysisReport


def test_finalize_clean_report_resets_score_and_violations_alias() -> None:
    report = AnalysisReport("clean.py")
    report.penalize(10)
    assert report.finalize() is report
    assert report["score"] == 100
    assert report.violations == []


def test_violations_returns_copy_of_findings() -> None:
    report = AnalysisReport("x.py")
    report.add("test", "minor", 1, "message")
    violations = report.violations
    assert violations == report["findings"]
    violations.clear()
    assert report.total == 1
