"""Tests for analysis_audit module."""

from __future__ import annotations

from services.analysis_audit import QualityAuditor


def test_quality_auditor_initialization() -> None:
    """Test that QualityAuditor can be initialized."""
    auditor = QualityAuditor()
    assert auditor is not None


def test_quality_auditor_has_audit_method() -> None:
    """Test that QualityAuditor has an audit method."""
    auditor = QualityAuditor()
    assert hasattr(auditor, "audit")
    assert callable(getattr(auditor, "audit"))


def test_audit_code_quality_method_exists() -> None:
    """Test that _audit_code_quality method exists."""
    auditor = QualityAuditor()
    assert hasattr(auditor, "_audit_code_quality")
    assert callable(getattr(auditor, "_audit_code_quality"))


def test_audit_tests_method_exists() -> None:
    """Test that _audit_tests method exists."""
    auditor = QualityAuditor()
    assert hasattr(auditor, "_audit_tests")
    assert callable(getattr(auditor, "_audit_tests"))


def test_audit_structure_method_exists() -> None:
    """Test that _audit_structure method exists."""
    auditor = QualityAuditor()
    assert hasattr(auditor, "_audit_structure")
    assert callable(getattr(auditor, "_audit_structure"))


def test_audit_documentation_method_exists() -> None:
    """Test that _audit_documentation method exists."""
    auditor = QualityAuditor()
    assert hasattr(auditor, "_audit_documentation")
    assert callable(getattr(auditor, "_audit_documentation"))


def test_finalize_method_exists() -> None:
    """Test that _finalize method exists."""
    auditor = QualityAuditor()
    assert hasattr(auditor, "_finalize")
    assert callable(getattr(auditor, "_finalize"))


import ast
from types import SimpleNamespace

import services.analysis_audit as audit_module


class FindingReport(dict):
    @property
    def total(self) -> int:
        return int(self["total"])


def test_finalize_uses_weighted_scores_and_zero_weight() -> None:
    auditor = QualityAuditor()
    report = {"code_quality": {"pct": 80}, "tests": {"pct": 60}}
    original = audit_module._WEIGHTS.copy()
    try:
        audit_module._WEIGHTS.clear()
        audit_module._WEIGHTS.update({"code_quality": 2, "tests": 1})
        assert auditor._finalize(report)["overall"] == 73.3
        audit_module._WEIGHTS.clear()
        assert auditor._finalize({})["overall"] == 0
    finally:
        audit_module._WEIGHTS.clear()
        audit_module._WEIGHTS.update(original)


def test_set_score_handles_zero_max() -> None:
    report: dict[str, object] = {}
    QualityAuditor()._set_score(report, "x", 3, 0, {"ok": True})
    assert report["x"] == {"score": 3, "max": 0, "pct": 0, "details": {"ok": True}}


def test_count_critical_findings_counts_only_known_categories() -> None:
    counts = {"syntax": 0, "io": 0}
    finding_report = FindingReport(
        total=4,
        findings=[
            {"severity": "critical", "category": "syntax"},
            {"severity": "critical", "category": "io"},
            {"severity": "warning", "category": "syntax"},
            {"severity": "critical", "category": "other"},
        ],
    )
    QualityAuditor()._count_critical_findings(finding_report, counts)
    assert counts == {"syntax": 1, "io": 1}


def test_count_critical_findings_returns_for_empty_report() -> None:
    counts = {"syntax": 0, "io": 0}
    QualityAuditor()._count_critical_findings(FindingReport(total=0, findings=[]), counts)
    assert counts == {"syntax": 0, "io": 0}


def test_parse_pytest_counts_and_ignores_invalid_values() -> None:
    counts = QualityAuditor()._parse_pytest_counts("10 passed 2 failed 1 errors\ninvalid passed failed errors")
    assert counts == {"passed": 10, "failed": 2, "errors": 1}


def test_store_count_ignores_invalid_integer() -> None:
    counts = {"passed": 0, "failed": 0, "errors": 0}
    QualityAuditor()._store_count(counts, ["bad", "passed"], 1, "passed")
    assert counts["passed"] == 0


def test_run_pytest_handles_os_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise OSError("pytest unavailable")

    monkeypatch.setattr(audit_module.subprocess, "run", fail)
    result = QualityAuditor()._run_pytest()
    assert result["error"] == "pytest unavailable"
    assert result["pass_pct"] == 0


def test_py_module_names_handles_missing_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_module, "_PROJECT_ROOT", str(tmp_path))
    assert QualityAuditor()._py_module_names("missing") == []
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "_private.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    assert sorted(QualityAuditor()._py_module_names("pkg")) == ["_private.py", "a.py"]


def test_register_import_accepts_existing_and_reports_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_module, "_PROJECT_ROOT", str(tmp_path))
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "present.py").write_text("", encoding="utf-8")
    auditor = QualityAuditor()
    issues: list[str] = []
    checked: set[tuple[str, str]] = set()
    auditor._register_import("x.py", "services.present", "bad", issues, checked)
    auditor._register_import("x.py", "services.missing", "missing", issues, checked)
    auditor._register_import("x.py", "external", "ignored", issues, checked)
    auditor._register_import("x.py", "services.missing", "missing", issues, checked)
    assert issues == ["x.py: missing"]
    assert len(checked) == 2


def test_scan_file_imports_reports_syntax_and_os_errors(tmp_path) -> None:
    auditor = QualityAuditor()
    issues: list[str] = []
    checked: set[tuple[str, str]] = set()
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    auditor._scan_file_imports(str(bad), issues, checked)
    auditor._scan_file_imports(str(tmp_path / "missing.py"), issues, checked)
    assert len(issues) == 2
    assert all("impossible de parser" in issue for issue in issues)


def test_has_docstring_and_invalid_file(tmp_path) -> None:
    auditor = QualityAuditor()
    documented = tmp_path / "documented.py"
    documented.write_text('"""module docs"""\n', encoding="utf-8")
    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(:\n", encoding="utf-8")
    assert auditor._has_docstring(str(documented)) is True
    assert auditor._has_docstring(str(invalid)) is False
    assert auditor._has_docstring(str(tmp_path / "missing.py")) is False


def test_doc_presence_and_docstring_coverage(tmp_path, monkeypatch) -> None:
    auditor = QualityAuditor()
    monkeypatch.setattr(audit_module, "_PROJECT_ROOT", str(tmp_path))
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "glossaire.md").write_text("glossary", encoding="utf-8")
    assert dict(auditor._audit_doc_presence()) == {
        "README.md": "present",
        "CHANGELOG.md": "manquant",
        "LICENSE": "manquant",
        "CONTRIBUTING.md": "manquant",
        "docs/glossaire.md": "present",
    }
    source = tmp_path / "source.py"
    source.write_text('"""docs"""\n', encoding="utf-8")
    monkeypatch.setattr(audit_module, "_source_py_files", lambda: [str(source)])
    assert auditor._audit_docstring_coverage() == 100.0


def test_find_dead_files_skips_init_scripts_and_main(tmp_path, monkeypatch) -> None:
    auditor = QualityAuditor()
    monkeypatch.setattr(audit_module, "_PROJECT_ROOT", str(tmp_path))
    init = tmp_path / "__init__.py"
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "tool.py"
    main = tmp_path / "main.py"
    dead = tmp_path / "dead.py"
    for path, content in {
        init: "",
        script: "",
        main: 'if __name__ == "__main__":\n    pass\n',
        dead: "value = 1\n",
    }.items():
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(
        audit_module,
        "_source_py_files",
        lambda: [str(init), str(script), str(main), str(dead)],
    )
    assert auditor._find_dead_files() == [str(dead)]


def test_audit_tests_handles_missing_test_directory(tmp_path, monkeypatch) -> None:
    report: dict[str, object] = {}
    monkeypatch.setattr(audit_module, "_TEST_DIR", str(tmp_path / "missing"))
    QualityAuditor()._audit_tests(report)
    assert report["tests"]["details"]["error"] == "Répertoire tests/ introuvable"


class AnalysisResult(dict):
    @property
    def total(self) -> int:
        return int(self["total"])


def test_source_py_files_deduplicates_and_sorts(monkeypatch) -> None:
    monkeypatch.setattr(audit_module, "_SOURCE_DIRS", ["a", "b"])
    monkeypatch.setattr(
        audit_module,
        "_py_files",
        lambda directory: {"a": ["z.py", "a.py"], "b": ["a.py", "m.py"]}[directory],
    )
    assert audit_module._source_py_files() == ["a.py", "m.py", "z.py"]


def test_audit_code_quality_aggregates_analyzer_results(tmp_path, monkeypatch) -> None:
    source = tmp_path / "module.py"
    source.write_text("x = 1\n", encoding="utf-8")
    auditor = QualityAuditor()
    monkeypatch.setattr(audit_module, "_source_py_files", lambda: [str(source)])
    monkeypatch.setattr(audit_module, "_count_lines", lambda _: 7)
    auditor._analyzer.analyze_file = lambda _: AnalysisResult(score=82, findings=[], total=0)
    report: dict[str, object] = {}
    auditor._audit_code_quality(report)
    assert report["code_quality"]["details"] == {
        "files_analyzed": 1,
        "total_lines": 7,
        "total_findings": 0,
        "avg_score": 82,
        "syntax_errors": 0,
        "io_errors": 0,
    }


def test_audit_tests_computes_composite_and_preserves_pytest_error(tmp_path, monkeypatch) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    source = tmp_path / "module.py"
    source.write_text("x = 1\n", encoding="utf-8")
    auditor = QualityAuditor()
    monkeypatch.setattr(audit_module, "_TEST_DIR", str(tests_dir))
    monkeypatch.setattr(audit_module, "_source_py_files", lambda: [str(source)])
    monkeypatch.setattr(audit_module, "_py_files", lambda _: ["test_module.py"])
    auditor._analyzer.check_test_exists = lambda _: {"test_found": True}
    monkeypatch.setattr(
        auditor,
        "_run_pytest",
        lambda: {"total": 2, "passed": 1, "failed": 1, "errors": 0, "pass_pct": 50, "error": "warning"},
    )
    report: dict[str, object] = {}
    auditor._audit_tests(report)
    assert report["tests"]["pct"] == 75.0
    assert report["tests"]["details"]["pytest_error"] == "warning"


def test_audit_structure_reports_all_checks(tmp_path, monkeypatch) -> None:
    (tmp_path / "controllers" / "routes").mkdir(parents=True)
    (tmp_path / "controllers" / "router.py").write_text("", encoding="utf-8")
    (tmp_path / "controllers" / "routes" / "home.py").write_text("", encoding="utf-8")
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "core.py").write_text("", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(audit_module, "_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(audit_module, "_TEST_DIR", str(tmp_path / "tests"))
    monkeypatch.setattr(audit_module, "_source_py_files", lambda: [])
    auditor = QualityAuditor()
    monkeypatch.setattr(auditor, "_find_dead_files", lambda: [])
    report: dict[str, object] = {}
    auditor._audit_structure(report)
    assert report["structure"]["details"]["checks_passed"] == 7
    assert report["structure"]["pct"] == 100.0


def test_audit_documentation_aggregates_presence_and_docstrings(monkeypatch) -> None:
    auditor = QualityAuditor()
    monkeypatch.setattr(
        auditor,
        "_audit_doc_presence",
        lambda: [("README.md", "present"), ("LICENSE", "manquant")],
    )
    monkeypatch.setattr(auditor, "_audit_docstring_coverage", lambda: 75.0)
    monkeypatch.setattr(audit_module, "_source_py_files", lambda: ["a.py", "b.py"])
    report: dict[str, object] = {}
    auditor._audit_documentation(report)
    assert report["documentation"]["score"] == 60.0
    assert report["documentation"]["details"]["files_with_docstrings"] == 1


def test_has_docstring_finds_function_or_class_docstring(tmp_path) -> None:
    auditor = QualityAuditor()
    function_file = tmp_path / "function.py"
    function_file.write_text('def f():\n    """docs"""\n', encoding="utf-8")
    class_file = tmp_path / "class.py"
    class_file.write_text('class C:\n    """docs"""\n', encoding="utf-8")
    assert auditor._has_docstring(str(function_file)) is True
    assert auditor._has_docstring(str(class_file)) is True


def test_audit_orchestrates_all_sections(monkeypatch) -> None:
    auditor = QualityAuditor()
    calls: list[str] = []
    for name in ("_audit_code_quality", "_audit_tests", "_audit_structure", "_audit_documentation"):
        monkeypatch.setattr(
            auditor,
            name,
            lambda report, name=name: calls.append(name),
        )
    monkeypatch.setattr(auditor, "_finalize", lambda report: {"overall": 99})
    assert auditor.audit() == {"overall": 99}
    assert calls == [
        "_audit_code_quality",
        "_audit_tests",
        "_audit_structure",
        "_audit_documentation",
    ]


def test_parse_pytest_counts_skips_blank_lines() -> None:
    assert QualityAuditor()._parse_pytest_counts("\n\n") == {
        "passed": 0,
        "failed": 0,
        "errors": 0,
    }


def test_run_pytest_parses_success(monkeypatch) -> None:
    monkeypatch.setattr(
        audit_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout="2 passed 1 failed", stderr=""),
    )
    result = QualityAuditor()._run_pytest()
    assert result == {
        "total": 3,
        "passed": 2,
        "failed": 1,
        "errors": 0,
        "pass_pct": 66.7,
    }


def test_check_imports_delegates_each_file(monkeypatch) -> None:
    auditor = QualityAuditor()
    seen: list[str] = []
    monkeypatch.setattr(
        auditor,
        "_scan_file_imports",
        lambda fp, issues, checked: seen.append(fp),
    )
    assert auditor._check_imports(["a.py", "b.py"]) == []
    assert seen == ["a.py", "b.py"]


def test_scan_file_imports_visits_import_nodes(tmp_path, monkeypatch) -> None:
    source = tmp_path / "imports.py"
    source.write_text(
        "import services.present\nfrom controllers import router\n",
        encoding="utf-8",
    )
    auditor = QualityAuditor()
    seen: list[str] = []
    monkeypatch.setattr(
        auditor,
        "_register_node_import",
        lambda fp, node, issues, checked: seen.append(type(node).__name__),
    )
    issues: list[str] = []
    auditor._scan_file_imports(str(source), issues, set())
    assert [name for name in seen if name in {"Import", "ImportFrom"}] == ["Import", "ImportFrom"]


def test_register_node_import_handles_import_and_import_from(monkeypatch) -> None:
    auditor = QualityAuditor()
    calls: list[str] = []
    monkeypatch.setattr(
        auditor,
        "_register_import",
        lambda fp, mod, label, issues, checked: calls.append(f"{fp}:{mod}:{label}"),
    )
    issues: list[str] = []
    checked: set[tuple[str, str]] = set()
    auditor._register_node_import(
        "source.py",
        ast.parse("import services.alpha").body[0],
        issues,
        checked,
    )
    auditor._register_node_import(
        "source.py",
        ast.parse("from controllers import router").body[0],
        issues,
        checked,
    )
    assert calls == [
        "source.py:services.alpha:import services.alpha échoué",
        "source.py:controllers:from controllers import ... échoué",
    ]


def test_find_dead_files_logs_unreadable_path(tmp_path, monkeypatch) -> None:
    auditor = QualityAuditor()
    unreadable = tmp_path / "unreadable.py"
    unreadable.mkdir()
    monkeypatch.setattr(audit_module, "_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(audit_module, "_source_py_files", lambda: [str(unreadable)])
    assert auditor._find_dead_files() == []
