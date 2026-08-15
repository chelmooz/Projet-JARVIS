from __future__ import annotations

from services.analysis import Analyzer


def test_analyze_file_missing_reports_io_error(tmp_path) -> None:
    report = Analyzer().analyze_file(str(tmp_path / "missing.py"))
    assert report["summary"]["critical"] == 1
    assert report["score"] == 50


def test_analyze_file_syntax_error(tmp_path) -> None:
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n", encoding="utf-8")
    report = Analyzer().analyze_file(str(path))
    assert report["summary"]["critical"] == 1
    assert "Erreur de syntaxe" in report["findings"][0]["message"]


def test_analyze_file_delegates_all_analyzers_and_finalizes(tmp_path) -> None:
    path = tmp_path / "clean.py"
    path.write_text('"""doc"""\ndef clean(value):\n    """Return value."""\n    return value\n', encoding="utf-8")
    report = Analyzer().analyze_file(str(path))
    assert report["path"] == str(path)
    assert "summary" in report


def test_check_test_exists_and_review_alias(tmp_path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("x = 1\n", encoding="utf-8")
    analyzer = Analyzer()
    assert analyzer.check_test_exists(str(path))["test_found"] is False
    assert analyzer.review_file(str(path))["path"] == str(path)


def test_analyze_project_skips_dunder_files(monkeypatch, tmp_path) -> None:
    files = [str(tmp_path / "a.py"), str(tmp_path / "__init__.py")]
    monkeypatch.setattr("services.analysis._py_files", lambda root: files)
    analyzer = Analyzer()
    reports = analyzer.analyze_project(str(tmp_path))
    assert [report["path"] for report in reports] == [files[0]]


def test_global_report_empty_project(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("services.analysis._py_files", lambda root: [])
    result = Analyzer().generate_global_report(str(tmp_path))
    assert result["files_analyzed"] == 0
    assert result["average_score"] == 0.0
    assert result["reports"] == []


def test_global_report_aggregates_reports(monkeypatch, tmp_path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr("services.analysis._py_files", lambda root: [str(source)])
    result = Analyzer().generate_global_report(str(tmp_path))
    assert result["files_analyzed"] == 1
    assert result["total_findings"] >= 0
    assert 0.0 <= result["coverage_pct"] <= 100.0
    assert result["elapsed_s"] >= 0.0


def test_global_report_counts_files_with_tests(monkeypatch, tmp_path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr("services.analysis._py_files", lambda root: [str(source)])
    monkeypatch.setattr(Analyzer, "check_test_exists", lambda self, path: {"test_found": True})
    result = Analyzer().generate_global_report(str(tmp_path))
    assert result["files_with_tests"] == 1
    assert result["coverage_pct"] == 100.0
