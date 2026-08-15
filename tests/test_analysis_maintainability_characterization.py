from __future__ import annotations

import ast

from services.analysis_maintainability import MaintainabilityAnalyzer
from services.analysis_report import AnalysisReport


def test_cyclomatic_complexity_flags_if_loop_except_and_boolops() -> None:
    conditions = "\n".join(f"    if value{i} and other{i}:\n        pass" for i in range(6))
    source = f"def complex():\n{conditions}\n"
    report = AnalysisReport("x.py")
    MaintainabilityAnalyzer()._check_cyclomatic_complexity(report, ast.parse(source))
    assert any("Complexité cyclomatique" in finding["message"] for finding in report["findings"])


def test_walk_local_does_not_enter_nested_function() -> None:
    tree = ast.parse("def outer():\n    if x:\n        pass\n    def inner():\n        if y:\n            pass\n")
    nodes = list(MaintainabilityAnalyzer()._walk_local(tree.body[0]))
    assert sum(isinstance(node, ast.If) for node in nodes) == 1


def test_code_duplication_flags_non_adjacent_blocks_and_ignores_comments() -> None:
    block = ["x = 1", "y = 2", "z = 3"]
    lines = block + ["# separator"] * 4 + block
    report = AnalysisReport("x.py")
    MaintainabilityAnalyzer()._check_code_duplication(report, lines)
    assert report.total == 1


def test_code_duplication_ignores_adjacent_and_filtered_blocks() -> None:
    report = AnalysisReport("x.py")
    lines = ["x = 1", "y = 2", "z = 3"] * 2 + ["# comment"] * 3
    MaintainabilityAnalyzer()._check_code_duplication(report, lines)
    assert report.total == 0


def test_too_many_branches_and_naked_except() -> None:
    conditions = "\n".join(f"    if value{i}:\n        pass" for i in range(10))
    source = f"def branched():\n{conditions}\n"
    report = AnalysisReport("x.py")
    analyzer = MaintainabilityAnalyzer()
    analyzer._check_too_many_branches(report, ast.parse(source))
    analyzer._check_naked_except(report, ["try:", "    pass", "except:", "    pass"])
    assert any("Trop de branches" in finding["message"] for finding in report["findings"])
    assert any("except: nu" in finding["message"] for finding in report["findings"])


def test_check_clean_source_has_no_findings() -> None:
    report = AnalysisReport("x.py")
    MaintainabilityAnalyzer().check(report, ast.parse("def f(x):\n    return x\n"), ["def f(x):", "    return x"])
    assert report.total == 0
