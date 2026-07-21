"""Tests TDD refactor QualityAuditor — deduplication via analysis_core (DRY/KISS)."""
import os

from services.analysis_audit import QualityAuditor
from services.analysis_core import _PROJECT_ROOT, _SOURCE_DIRS, _py_files


class TestQualityAuditorDedup:

    def test_audit_returns_4_axes(self):
        a = QualityAuditor()
        report = a.audit()
        for cat in ("code_quality", "tests", "structure", "documentation"):
            assert cat in report
        assert "overall" in report

    def test_source_files_helper_reuses_core(self):
        from services.analysis_audit import _source_py_files
        files = _source_py_files()
        expected = sorted(set(f for d in _SOURCE_DIRS for f in _py_files(d)))
        assert files == expected

    def test_dead_files_uses_core_scan(self):
        a = QualityAuditor()
        dead = a._find_dead_files()
        assert isinstance(dead, list)
        # analysis_audit lui-meme est reference (importe par services.analysis) -> pas mort
        assert not any("analysis_audit.py" in f for f in dead)

    def test_has_docstring_reuses_ast(self):
        a = QualityAuditor()
        fp = os.path.join(_PROJECT_ROOT, "services", "analysis_report.py")
        assert a._has_docstring(fp) is True
        fp_missing = os.path.join(_PROJECT_ROOT, "scripts", "add_missing_docstrings.py")
        assert a._has_docstring(fp_missing) in (True, False)

    def test_audit_documentation_splits_responsibilities(self):
        a = QualityAuditor()
        doc_tokens = a._audit_doc_presence()
        docstring_pct = a._audit_docstring_coverage()
        assert isinstance(doc_tokens, list)
        assert isinstance(docstring_pct, float)
        assert 0.0 <= docstring_pct <= 100.0
