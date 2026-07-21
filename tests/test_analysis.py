"""Tests dédiés à services/analysis.py (Analyzer).

Comble le trou TDD identifié par AUDIT_CLEAN_CODE_KISS_SOLID_TDD.md §4 :
`find tests -iname "*analysis*"` ne renvoyait aucun résultat avant ce fichier,
alors que services/analysis.py (890 lignes) fait office de gate qualité pour
tout le reste du repo.

tests/test_code_review.py couvre déjà une bonne partie de la sécurité et de
la performance via l'alias `review_file`. Ce fichier se concentre sur :
- les règles coding_standard non couvertes ailleurs (naming, docstrings,
  SRP, nesting, params, longueur fonction/fichier, else superflu, ratio
  commentaires) ;
- check_test_exists (API publique dédiée) ;
- les 2 régressions de faux positifs corrigées dans _check_dangerous_calls
  (cf. AUDIT_CLEAN_CODE_KISS_SOLID_TDD.md §4 — dogfooding) : re.compile(...)
  et __import__(...) encadré d'un try/except ImportError ne doivent plus
  être signalés comme risque d'exécution de code arbitraire.
"""
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


def _cleanup(*paths: str):
    for p in paths:
        with contextlib.suppress(OSError):
            os.unlink(p)


def _findings(report, category: str = None, message_contains: str = None):
    findings = report["findings"]
    if category is not None:
        findings = [f for f in findings if f["category"] == category]
    if message_contains is not None:
        findings = [f for f in findings if message_contains in f["message"]]
    return findings


# ── Régressions faux positifs (audit §4 — dogfooding) ──────────────────────


def test_re_compile_not_flagged_as_dangerous_call(analyzer):
    """re.compile(...) est un appel stdlib sûr, pas le compile() builtin dangereux."""
    code = "import re\n_PATTERN = re.compile(r'abc')\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        dangerous = _findings(r, message_contains="Appel dangereux")
        assert dangerous == [], f"re.compile ne doit pas etre signale : {dangerous}"
    finally:
        _cleanup(path)


def test_bare_compile_still_flagged_as_dangerous_call(analyzer):
    """Le compile() builtin nu (pas un appel de méthode) reste bien détecté."""
    code = "code_obj = compile(source, 'string', 'exec')\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        dangerous = _findings(r, message_contains="Appel dangereux")
        assert len(dangerous) >= 1
    finally:
        _cleanup(path)


def test_import_check_pattern_not_flagged(analyzer):
    """__import__ encadré d'un try/except ImportError = validation de
    résolvabilité d'un import, pas une exécution de code arbitraire
    (pattern utilisé par Analyzer._check_imports lui-même)."""
    code = (
        "def check(mod):\n"
        "    try:\n"
        "        __import__(mod)\n"
        "    except ImportError:\n"
        "        return False\n"
        "    return True\n"
    )
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        dangerous = _findings(r, message_contains="Appel dangereux")
        assert dangerous == [], f"__import__ dans try/except ImportError ne doit pas etre signale : {dangerous}"
    finally:
        _cleanup(path)


def test_bare_import_dunder_still_flagged_outside_try_except(analyzer):
    """__import__ hors contexte try/except ImportError reste détecté."""
    code = "mod = __import__(user_supplied_name)\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        dangerous = _findings(r, message_contains="Appel dangereux")
        assert len(dangerous) >= 1
    finally:
        _cleanup(path)


def test_eval_still_flagged(analyzer):
    """Non-régression : eval() nu doit toujours être détecté (dangerous_calls)."""
    code = "result = eval(user_input)\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        dangerous = _findings(r, message_contains="Appel dangereux")
        assert len(dangerous) >= 1
    finally:
        _cleanup(path)


# ── coding_standard : naming ────────────────────────────────────────────────


def test_camelcase_function_name_flagged(analyzer):
    code = "def maFonction():\n    return 1\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="snake_case")
        assert any("maFonction" in f["message"] for f in findings)
    finally:
        _cleanup(path)


def test_snake_case_function_name_passes(analyzer):
    code = "def ma_fonction():\n    \"\"\"Docstring.\"\"\"\n    return 1\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="snake_case")
        assert findings == []
    finally:
        _cleanup(path)


def test_private_function_name_not_checked(analyzer):
    """Les noms préfixés '_' (privés/dunder) ne sont pas soumis à la règle snake_case publique."""
    code = "def _maFonctionPrivee():\n    \"\"\"Docstring.\"\"\"\n    return 1\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="snake_case")
        assert findings == []
    finally:
        _cleanup(path)


# ── coding_standard : docstrings ────────────────────────────────────────────


def test_missing_docstring_flagged(analyzer):
    code = "def ma_fonction():\n    return 1\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="docstring manquante")
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_dunder_method_docstring_not_required(analyzer):
    code = "class Foo:\n    def __init__(self):\n        self.x = 1\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="__init__")
        assert findings == []
    finally:
        _cleanup(path)


# ── coding_standard : SRP (trop de méthodes / trop d'appels distincts) ──────


def test_class_with_too_many_methods_flagged_srp(analyzer):
    methods = "\n".join(f"    def m{i}(self):\n        \"\"\"Doc.\"\"\"\n        return {i}\n" for i in range(20))
    code = f"class BigClass:\n    \"\"\"Doc.\"\"\"\n{methods}"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="violation SRP")
        assert any("BigClass" in f["message"] for f in findings)
    finally:
        _cleanup(path)


def test_small_class_not_flagged_srp(analyzer):
    code = "class SmallClass:\n    \"\"\"Doc.\"\"\"\n\n    def m1(self):\n        \"\"\"Doc.\"\"\"\n        return 1\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="violation SRP")
        assert findings == []
    finally:
        _cleanup(path)


# ── coding_standard : nombre de paramètres ──────────────────────────────────


def test_too_many_params_flagged(analyzer):
    code = "def f(a, b, c, d, e):\n    \"\"\"Doc.\"\"\"\n    return a + b + c + d + e\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="parametres")
        assert len(findings) >= 1
    finally:
        _cleanup(path)


def test_self_not_counted_in_params(analyzer):
    """`self` ne doit pas compter dans le total de paramètres."""
    code = "class C:\n    def f(self, a, b):\n        \"\"\"Doc.\"\"\"\n        return a + b\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="parametres")
        assert findings == []
    finally:
        _cleanup(path)


# ── coding_standard : imbrication (KISS) ────────────────────────────────────


def test_deep_nesting_flagged(analyzer):
    code = (
        "def f(a, b, c, d):\n"
        "    \"\"\"Doc.\"\"\"\n"
        "    if a:\n"
        "        if b:\n"
        "            if c:\n"
        "                if d:\n"
        "                    return 1\n"
        "    return 0\n"
    )
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="imbrication")
        assert len(findings) >= 1
    finally:
        _cleanup(path)


# ── coding_standard : longueur fonction/fichier ─────────────────────────────


def test_long_function_flagged(analyzer):
    body = "\n".join(f"    x{i} = {i}" for i in range(25))
    code = f"def f():\n    \"\"\"Doc.\"\"\"\n{body}\n    return x0\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="lignes")
        assert any("Fonction" in f["message"] for f in findings)
    finally:
        _cleanup(path)


# ── coding_standard : else superflu ──────────────────────────────────────────


def test_superfluous_else_after_early_return_flagged(analyzer):
    code = (
        "def f(a):\n"
        "    \"\"\"Doc.\"\"\"\n"
        "    if a:\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n"
    )
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        findings = _findings(r, category="coding_standard", message_contains="else superflu")
        assert len(findings) >= 1
    finally:
        _cleanup(path)


# ── testing : détection de fichier de test manquant ─────────────────────────


def test_check_test_exists_reports_missing(analyzer, tmp_path):
    src = tmp_path / "services"
    src.mkdir()
    fake_module = src / "totally_untested_module.py"
    fake_module.write_text("x = 1\n", encoding="utf-8")
    result = analyzer.check_test_exists(str(fake_module))
    assert result["test_found"] is False


def test_check_test_exists_finds_matching_test(analyzer, tmp_path):
    src = tmp_path / "services"
    src.mkdir()
    fake_module = src / "mon_module.py"
    fake_module.write_text("x = 1\n", encoding="utf-8")
    # Candidat vérifié par check_test_exists : <dir>/tests/test_<fichier>.py
    tests_dir = src / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mon_module.py").write_text("def test_x(): pass\n", encoding="utf-8")
    result = analyzer.check_test_exists(str(fake_module))
    assert result["test_found"] is True


# ── clean_code_passes / score global (non-régression) ───────────────────────


def test_analyze_file_returns_full_report_shape(analyzer):
    """Vérifie la forme du rapport retourné par analyze_file (contrat public)."""
    code = "x = 1\n"
    path = _write_temp(code)
    try:
        r = analyzer.analyze_file(path)
        assert set(r.keys()) >= {"path", "findings", "score", "summary"}
        assert r["summary"]["total"] == len(r["findings"])
        assert 0 <= r["score"] <= 100
    finally:
        _cleanup(path)
