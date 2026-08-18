"""Tests MT-KB-L3f — convertisseur pkg_resources (pypa/setuptools) → JSONL @dev.

Vérifie le schéma 5 clés, la licence MIT, l'extraction des docstrings de
fonctions (ex: get_distribution) et l'unicité des ids (id = ``setuptools/<fn>``).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.convert_setuptools_run import extract_pkg_resources

PKG_FACTICE = '''"""pkg_resources - Fake source for tests."""

import warnings


def get_distribution(dist):
    """Return a current Distribution object for a RequirementSpecifier.

    Attempts to load the distribution from the working set.
    """
    if dist is None:
        raise ValueError("dist must be provided")
    warnings.warn("deprecated", DeprecationWarning)
    return dist


def resource_filename(package_or_requirement, resource_name):
    """Return file system path for a resource."""
    return resource_name
'''


def _write_pkg(tmp_path: Path, content: str = PKG_FACTICE) -> Path:
    path = tmp_path / "pkg_resources" / "__init__.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestSetuptoolsConverter:
    def test_function_extracts_valid_jsonl_entry(self, tmp_path: Path) -> None:
        """Schéma 5 clés, agent @dev, licence MIT, id setuptools/<fn>, docstring."""
        path = _write_pkg(tmp_path)

        entries = extract_pkg_resources(path)

        assert len(entries) == 2
        entry = next(e for e in entries if e["id"] == "setuptools/get_distribution")
        assert set(entry.keys()) == {"id", "agent", "source", "text", "metadata"}
        assert entry["agent"] == "@dev"
        assert entry["source"] == "setuptools"
        assert entry["metadata"]["license"] == "MIT"
        assert "Distribution" in entry["text"]
        assert "deprecated" in entry["text"].lower()

    def test_unique_ids_and_metadata_function(self, tmp_path: Path) -> None:
        """Id uniques, metadata.function renseigné."""
        path = _write_pkg(tmp_path)

        entries = extract_pkg_resources(path)

        ids = [e["id"] for e in entries]
        assert len(ids) == len(set(ids)), f"ids dupliqués: {ids}"
        assert {e["metadata"]["function"] for e in entries} == {"get_distribution", "resource_filename"}
        assert all(e["agent"] == "@dev" for e in entries)
