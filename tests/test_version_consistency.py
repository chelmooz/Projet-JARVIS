"""Tests Fix #6 — Vérifie que la version du projet est cohérente partout.

L'audit a repéré une incohérence 5.0 vs 5.1 entre config/constants.py et
README.md. Ce test compare la valeur canonique (config.constants.VERSION)
avec ce qui est écrit dans README.md et, si présent, dans pyproject.toml.
"""
import os
import re

import pytest

PROJECT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
README_PATH = os.path.join(PROJECT_ROOT, "README.md")
PYPROJECT_PATH = os.path.join(PROJECT_ROOT, "pyproject.toml")

VERSION_PATTERN = re.compile(r"\bv?(\d+\.\d+(?:\.\d+)?)\b")


def _canonical_version():
    try:
        from config import constants
    except ImportError as exc:
        pytest.skip(f"Impossible d'importer config.constants : {exc}")
    version = getattr(constants, "VERSION", None)
    if not version:
        pytest.skip("config.constants.VERSION introuvable.")
    return str(version)


class TestVersionConsistency:

    def test_readme_matches_canonical_version(self):
        """La première mention de version dans README.md doit matcher VERSION."""
        canonical = _canonical_version()

        if not os.path.exists(README_PATH):
            pytest.skip(f"README.md introuvable à {README_PATH}")

        with open(README_PATH, encoding="utf-8") as f:
            content = f.read()

        matches = VERSION_PATTERN.findall(content)
        if not matches:
            pytest.skip("Aucune mention de version trouvée dans README.md.")

        assert canonical in matches, (
            f"config.constants.VERSION={canonical!r} mais README.md mentionne "
            f"d'autres versions : {sorted(set(matches))}. Unifier (Fix #6)."
        )

    def test_pyproject_version_matches_canonical_version_if_present(self):
        """Si pyproject.toml déclare [project].version, elle doit matcher VERSION."""
        canonical = _canonical_version()

        try:
            import tomllib
        except ModuleNotFoundError:
            pytest.skip("tomllib indisponible (Python < 3.11)")

        if not os.path.exists(PYPROJECT_PATH):
            pytest.skip(f"pyproject.toml introuvable à {PYPROJECT_PATH}")

        with open(PYPROJECT_PATH, "rb") as f:
            data = tomllib.load(f)

        pyproject_version = data.get("project", {}).get("version")
        if not pyproject_version:
            pytest.skip("pyproject.toml ne déclare pas [project].version (probablement dynamic).")

        assert str(pyproject_version) == canonical, (
            f"pyproject.toml [project].version={pyproject_version!r} ne correspond "
            f"pas à config.constants.VERSION={canonical!r}."
        )
