"""Tests pour Code Review — sécurité, performance, maintenabilité."""
import contextlib
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.analysis import Analyzer as CodeReviewAnalyzer


@pytest.fixture
def analyzer():
    return CodeReviewAnalyzer()


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
        r = analyzer.review_file(path)
        assert r["score"] >= 97, f"Score should be >=97, got {r['score']}"
        non_testing = [f for f in r["findings"] if f["category"] != "testing"]
        assert len(non_testing) == 0
    finally:
        _cleanup(path)


# ── Security ──

def test_hardcoded_password(analyzer):
    code = 'DB_PASSWORD = "supersecret123"\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if f["category"] == "security"]
        assert len(findings) >= 1, "Should detect hardcoded password"
        assert r["score"] < 100
    finally:
        _cleanup(path)


def test_hardcoded_aws_key(analyzer):
    code = 'AWS_KEY = "AKIA1234567890123456"\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "aws_key" in f["message"]]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_dangerous_eval(analyzer):
    code = 'result = eval(user_input)\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "eval" in f["message"]]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_dangerous_pickle(analyzer):
    code = 'data = pickle.loads(raw)\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "pickle" in f["message"]]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_unsafe_yaml(analyzer):
    code = 'cfg = yaml.load(content)\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "yaml" in f["message"]]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_path_traversal(analyzer):
    code = 'data = open(request.args.get("file")).read()\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "Path traversal" in f["message"]]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_github_token(analyzer):
    code = 'GH_TOKEN = "ghp_123456789012345678901234567890123456"\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "secret" in f["message"] or "token" in f["message"].lower()]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_xss_risk(analyzer):
    code = 'element.innerHTML = user_input\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "XSS" in f["message"]]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


# ── Performance ──

def test_nested_loops(analyzer):
    code = '''def process(matrix):
    for row in matrix:
        for col in row:
            for val in col:
                print(val)
'''
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if f["category"] == "performance"]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_list_wrapper_superfluous(analyzer):
    code = 'result = list([x * 2 for x in range(10)])\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if "list" in f["message"] and "superflu" in f["message"]]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


# ── Maintainability ──

def test_high_cyclomatic_complexity(analyzer):
    code = '''def complex_func(a, b, c):
    if a:
        if b:
            return 1
        elif c:
            return 2
        else:
            return 3
    elif b:
        if a:
            return 4
        elif c:
            return 5
        else:
            return 6
    else:
        if a:
            return 7
        elif b:
            return 8
        elif c:
            return 9
        else:
            return 10
    return 0
'''
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if f["category"] == "maintainability"]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_code_duplication(analyzer):
    block = """def save_user(data):
    validate(data)
    db.insert(data)
    log.info("User saved")

def save_admin(data):
    validate(data)
    db.insert(data)
    log.info("User saved")
"""
    path = _write_temp(block)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if f["category"] == "maintainability"]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_no_test_file(analyzer):
    code = 'x = 1\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        findings = [f for f in r["findings"] if f["category"] == "testing"]
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_syntax_error_returns_report(analyzer):
    code = 'def broken(:\n    pass\n'
    path = _write_temp(code)
    try:
        r = analyzer.review_file(path)
        assert r["score"] <= 50
        assert any(f["category"] == "syntax" for f in r["findings"])
    finally:
        _cleanup(path)


def test_io_error_returns_report(tmp_path, analyzer):
    r = analyzer.review_file(str(tmp_path / "nonexistent" / "file.py"))
    assert r["score"] <= 50
    assert any(f["category"] == "io" for f in r["findings"])


# ── Route import ──

def test_route_imports():
    from controllers.routes.code_review import router
    paths = [r.path for r in router.routes]
    assert "/api/code-review/file" in paths
    assert "/api/code-review/project" in paths
