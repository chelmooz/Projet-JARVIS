from __future__ import annotations

import ast

from services.analysis_report import AnalysisReport
from services.analysis_security import SecurityAnalyzer


def run(code: str) -> AnalysisReport:
    report = AnalysisReport("sample.py")
    SecurityAnalyzer().check(report, code, ast.parse(code))
    return report


def test_hardcoded_secret_and_comment_are_distinguished() -> None:
    report = run("# password='secret'\npassword = 'secret'\n")
    assert report.total == 1
    assert report["findings"][0]["severity"] == "critical"


def test_dangerous_calls_and_safe_import_check() -> None:
    report = run("eval(user_input)\nexec(code)\n__import__(name)\n")
    assert report.total == 3
    safe = "try:\n    __import__(name)\nexcept ImportError:\n    pass\n"
    assert run(safe).total == 0
    assert SecurityAnalyzer._is_safe_import_check(safe.splitlines(), 2) is True
    assert SecurityAnalyzer._is_safe_import_check(["__import__(x)"], 1) is False


def test_pickle_and_yaml_load_are_reported() -> None:
    report = run("pickle.loads(data)\nyaml.load(data)\nmarshal.loads(data)\n")
    assert report.total >= 2
    assert any("désérialisation" in finding["message"] for finding in report["findings"])


def test_path_traversal_and_xss_are_reported() -> None:
    report = run("open(request.args)\nresponse.write(user_html)\nelement.innerHTML = user_html\n")
    messages = [finding["message"] for finding in report["findings"]]
    assert any("Path traversal" in message for message in messages)
    assert any("XSS" in message for message in messages)


def test_sql_injection_f_string_and_percent_format() -> None:
    report = run('cursor.execute(f"SELECT * FROM users WHERE id={user_id}")\ncursor.execute("SELECT %s" % user_id)\n')
    messages = [finding["message"] for finding in report["findings"]]
    assert any("f-string" in message for message in messages)
    assert any("% dans execute" in message for message in messages)


def test_sql_check_covers_raw_input_and_clean_query() -> None:
    report = run("db.raw_input(f\"SELECT {value}\")\ndb.execute('SELECT 1')\n")
    assert report.total == 1
    assert report["findings"][0]["line"] == 1


def test_check_empty_code_has_no_findings() -> None:
    report = run("")
    assert report.total == 0
    assert report["score"] == 100
