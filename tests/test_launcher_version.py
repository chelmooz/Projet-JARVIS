"""Tests launchers — version + chargement .env (audit DevOps 1.3 / 2.2 / 2.3).

Verifications statiques (pas d'execution shell) : les lanceurs Windows (.bat)
et Unix (.sh) affichent la meme VERSION que config.constants, le .sh charge le
.env, et le .bat ignore les commentaires (#) et les lignes sans '='.
"""
from pathlib import Path

from config.constants import VERSION

ROOT = Path(__file__).resolve().parent.parent


def test_bat_version_matches_constants():
    text = (ROOT / "launchers" / "JARVIS.bat").read_text(encoding="utf-8", errors="replace")
    assert f"v{VERSION}" in text


def test_sh_version_matches_constants():
    text = (ROOT / "launchers" / "JARVIS.sh").read_text(encoding="utf-8", errors="replace")
    assert f"v{VERSION}" in text


def test_sh_sources_env():
    text = (ROOT / "launchers" / "JARVIS.sh").read_text(encoding="utf-8", errors="replace")
    assert "set -a" in text
    assert '. "$ROOT/.env"' in text


def test_bat_env_parsing_skips_comments():
    text = (ROOT / "launchers" / "JARVIS.bat").read_text(encoding="utf-8", errors="replace")
    assert "eol=#" in text
    assert 'if not "%%b"==""' in text


def test_requirements_runtime_has_no_dev_tools():
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8", errors="replace")
    for pkg in ("pytest", "pytest-cov", "coverage", "ruff"):
        assert pkg not in text, f"{pkg} ne doit pas etre dans requirements.txt"


def test_requirements_dev_contains_dev_tools():
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8", errors="replace")
    for pkg in ("pytest", "pytest-cov", "coverage", "ruff"):
        assert pkg in text, f"{pkg} doit etre dans requirements-dev.txt"
