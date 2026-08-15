from __future__ import annotations

import ast

from services.analysis_report import AnalysisReport
from services.analysis_standards import CodingStandardsAnalyzer, TestExistenceChecker


def report_for(source: str, lines: list[str] | None = None) -> AnalysisReport:
    report = AnalysisReport("sample.py")
    tree = ast.parse(source)
    CodingStandardsAnalyzer().check(report, tree, lines if lines is not None else source.splitlines())
    return report


def messages(report: AnalysisReport) -> list[str]:
    return [finding["message"] for finding in report["findings"]]


def test_check_file_length_and_empty_lines() -> None:
    analyzer = CodingStandardsAnalyzer()
    report = AnalysisReport("x.py")
    analyzer._check_file_length(report, ["x"] * 501)
    analyzer._check_file_length(report, [])
    assert report.total == 1
    assert report["score"] == 95


def test_function_length_and_parameter_limits() -> None:
    source = "def long(" + ",".join(f"p{i}" for i in range(6)) + "):\n" + "\n".join("    pass" for _ in range(61))
    report = report_for(source)
    assert any("Fonction 'long'" in msg for msg in messages(report))
    assert any("parametres" in msg for msg in messages(report))


def test_async_function_and_nesting_limits() -> None:
    source = "async def f(a,b,c,d,e):\n    if a:\n        if b:\n            if c:\n                if d:\n                    return e\n"
    report = report_for(source)
    assert any("imbrication" in msg for msg in messages(report))
    assert any("parametres" in msg for msg in messages(report))


def test_naming_rules_accept_private_constants_and_flag_bad_names() -> None:
    report = report_for("BADName = 1\nGOOD_NAME = 2\n_private = 3\ndef BadName():\n    pass\n")
    assert any("Variable 'BADName'" in msg for msg in messages(report))
    assert any("Fonction 'BadName'" in msg for msg in messages(report))


def test_docstrings_skip_dunder_and_report_missing() -> None:
    report = report_for("class C:\n    def __init__(self):\n        pass\n    def method(self):\n        pass\n")
    assert any("C' : docstring manquante" in msg for msg in messages(report))
    assert any("method' : docstring manquante" in msg for msg in messages(report))
    assert not any("__init__" in msg for msg in messages(report))


def test_srp_class_and_function_topics() -> None:
    methods = "\n".join(f"    def m{i}(self):\n        pass" for i in range(16))
    calls = "\n".join(f"    call{i}()" for i in range(11))
    report = report_for(f"class C:\n{methods}\ndef f():\n{calls}\n")
    assert any("possible violation SRP" in msg for msg in messages(report))


def test_distinct_call_topics_handles_attributes_and_names() -> None:
    tree = ast.parse("def f():\n    obj.run()\n    helper()\n")
    node = tree.body[0]
    assert CodingStandardsAnalyzer()._distinct_call_topics(node) == {"run", "helper"}


def test_comments_ratio_and_else_with_early_return() -> None:
    analyzer = CodingStandardsAnalyzer()
    report = AnalysisReport("x.py")
    analyzer._check_comments_ratio(report, ["# comment"] * 4 + ["x = 1"])
    tree = ast.parse("def f(x):\n    if x:\n        return 1\n    else:\n        return 2\n")
    analyzer._check_else_usage(report, tree)
    assert report.total == 2


def test_else_usage_skips_nested_if() -> None:
    report = AnalysisReport("x.py")
    tree = ast.parse("if x:\n    return_value = 1\nelse:\n    if y:\n        return_value = 2\n")
    CodingStandardsAnalyzer()._check_else_usage(report, tree)
    assert report.total == 0


def test_check_pipeline_runs_all_rules_without_findings_for_clean_code() -> None:
    report = report_for('"""module"""\ndef clean(value: int) -> int:\n    """""Return value."""""\n    return value\n')
    assert report.total == 0
    assert report["score"] == 100


def test_test_existence_checker_check_and_resolve(tmp_path, monkeypatch) -> None:
    checker = TestExistenceChecker()
    source = tmp_path / "services" / "sample.py"
    source.parent.mkdir()
    source.write_text("", encoding="utf-8")
    candidate = tmp_path / "tests" / "test_sample.py"
    candidate.parent.mkdir()
    candidate.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "services.analysis_standards._resolve_test_candidates",
        lambda _: [str(candidate)],
    )
    report = AnalysisReport(str(source))
    checker.check(report, str(source))
    assert report.total == 0
    assert checker.resolve(str(source)) == {
        "source": str(source),
        "test_found": True,
        "test_paths": [str(candidate)],
    }


def test_test_existence_checker_reports_missing(tmp_path, monkeypatch) -> None:
    checker = TestExistenceChecker()
    monkeypatch.setattr("services.analysis_standards._resolve_test_candidates", lambda _: [])
    report = AnalysisReport(str(tmp_path / "missing.py"))
    checker.check(report, str(tmp_path / "missing.py"))
    assert report.total == 1
    assert checker.resolve("missing.py")["test_found"] is False


def test_function_length_skips_nodes_without_line_numbers() -> None:
    report = AnalysisReport("x.py")
    function = ast.parse("def f():\n    pass").body[0]
    function.lineno = None
    CodingStandardsAnalyzer()._check_function_length(report, ast.Module(body=[function], type_ignores=[]))
    assert report.total == 0


def test_variable_naming_accepts_snake_case() -> None:
    report = AnalysisReport("x.py")
    node = ast.parse("good_name = 1").body[0].targets[0]
    CodingStandardsAnalyzer()._check_variable_naming(report, node)
    assert report.total == 0


def test_comments_ratio_returns_for_empty_source() -> None:
    report = AnalysisReport("x.py")
    CodingStandardsAnalyzer()._check_comments_ratio(report, [])
    assert report.total == 0
