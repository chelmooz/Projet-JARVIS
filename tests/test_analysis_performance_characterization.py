from __future__ import annotations

import ast

from services.analysis_performance import PerformanceAnalyzer
from services.analysis_report import AnalysisReport


def run(source: str) -> AnalysisReport:
    report = AnalysisReport("performance.py")
    PerformanceAnalyzer().check(report, ast.parse(source))
    return report


def test_nested_loops_and_async_loop_are_reported() -> None:
    source = """async def f(items):
    for a in items:
        while a:
            async for b in items:
                for c in items:
                    pass
"""
    report = run(source)
    assert any("Boucle imbriquée" in finding["message"] for finding in report["findings"])


def test_nplusone_detects_db_calls_inside_for() -> None:
    report = run("def f(items):\n    for item in items:\n        db.get(item)\n        db.execute(item)\n")
    assert any("N+1" in finding["message"] for finding in report["findings"])


def test_list_comprehension_wrapped_in_list_is_reported() -> None:
    report = run("values = list([item for item in items])\n")
    assert report.total == 1
    assert report["findings"][0]["severity"] == "minor"


def test_repeated_attribute_calls_in_for_and_while() -> None:
    source = """def f(items):
    for item in items:
        service.fetch(item)
        service.fetch(item)
        service.fetch(item)
    while ready:
        cache.get(key)
        cache.get(key)
        cache.get(key)
"""
    report = run(source)
    assert sum("Appel répété" in finding["message"] for finding in report["findings"]) == 2


def test_clean_performance_source_has_no_findings() -> None:
    report = run("def f(items):\n    return (item for item in items)\n")
    assert report.total == 0
