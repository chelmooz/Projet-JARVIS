"""Tests pour analysis — analyse statique unifiée (ex-Kill Coding)."""
import contextlib
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.analysis import Analyzer


@pytest.fixture
def analyzer():
    return Analyzer()


def _write_temp(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
    return f.name


def _cleanup(path: str):
    with contextlib.suppress(OSError):
        os.unlink(path)


def test_clean_code_passes(analyzer):
    code = 'x = 1\ny = 2\n'
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert r["score"] >= 97
        non_testing = [f for f in r["findings"] if f["category"] != "testing"]
        assert len(non_testing) == 0
    finally:
        _cleanup(path)


def test_function_too_long(analyzer):
    code = '\n'.join([f'    a = {i}' for i in range(25)])
    code = 'def long_func():\n    """Doc."""\n' + code
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("lignes" in v["message"] for v in r["findings"])
        assert r["score"] < 100
    finally:
        _cleanup(path)


def test_too_many_params(analyzer):
    code = '''def bad_func(a, b, c, d, e):
    """Docstring."""
    return a + b + c + d + e
'''
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("parametres" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_bare_except(analyzer):
    code = '''def safe_func():
    """Docstring."""
    try:
        return 1 / 0
    except:
        return 0
'''
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("except:" in v["snippet"] for v in r["findings"] if v["category"] == "maintainability")
    finally:
        _cleanup(path)


def test_else_superfluous_with_early_return(analyzer):
    code = '''def process(x):
    """Docstring."""
    if x > 0:
        return x
    else:
        return 0
'''
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("else superflu" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_naming_snake_case(analyzer):
    code = '''def badFunctionName():
    """Docstring."""
    pass
'''
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("snake_case" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_missing_docstring(analyzer):
    code = 'def no_doc():\n    pass\n'
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("docstring manquante" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_excessive_nesting(analyzer):
    code = '''def deep_nest(x):
    """Docstring."""
    if x > 0:
        if x > 1:
            if x > 2:
                if x > 3:
                    return x
    return 0
'''
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("imbrication" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_check_test_exists_negative(tmp_path, analyzer):
    r = analyzer.check_test_exists(str(tmp_path / "nonexistent_dir_xyz" / "src" / "module.py"))
    assert r["test_found"] is False


def test_syntax_error_penalty(analyzer):
    code = 'def broken(:\n    pass\n'
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert r["score"] <= 50
        assert any(v["category"] == "syntax" for v in r["findings"])
    finally:
        _cleanup(path)


def test_file_too_long(analyzer):
    lines = [f"x = {i}\n" for i in range(600)]
    path = _write_temp("".join(lines))
    try:
        r = analyzer.analyze_file(path)
        assert any("Fichier trop long" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_srp_class_detected(analyzer):
    code = ''.join(f'    def m{i:02d}(self): pass\n' for i in range(16))
    code = 'class GodClass:\n    """Too many methods."""\n' + code
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert any("methodes" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_project_analysis_empty_dir(analyzer):
    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "empty.py"), "w", encoding="utf-8").close()
        report = analyzer.generate_global_report(root=tmp)
        assert report["files_analyzed"] >= 1


def test_comments_ratio_detected(analyzer):
    lines = ["# comment\n"] * 40 + ["x = 1\n"] * 20
    path = _write_temp("".join(lines))
    try:
        r = analyzer.analyze_file(path)
        assert any("commentaires" in v["message"] for v in r["findings"])
    finally:
        _cleanup(path)


def test_io_error_returns_report(tmp_path, analyzer):
    r = analyzer.analyze_file(str(tmp_path / "nonexistent" / "file.py"))
    assert r["score"] <= 50
    assert any(v["category"] == "io" for v in r["findings"])


def test_self_analysis(analyzer):
    path = os.path.join(os.path.dirname(__file__), "..", "services", "analysis.py")
    r = analyzer.analyze_file(path)
    assert r.total > 0
