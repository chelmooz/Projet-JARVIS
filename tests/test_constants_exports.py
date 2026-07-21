"""Tests d'export des constantes critiques — vérifie que __all__ est complet."""

import importlib
import sys

import pytest


def _reload_constants():
    """Recharge config.constants pour valider __all__ à l'état frais."""
    if "config.constants" in sys.modules:
        del sys.modules["config.constants"]
    return importlib.import_module("config.constants")


class TestMaxVectorDocsExport:
    """Vérifie que MAX_VECTOR_DOCS est défini ET exporté dans __all__."""

    def test_max_vector_docs_is_defined(self):
        """MAX_VECTOR_DOCS doit exister comme attribut du module."""
        constants = _reload_constants()
        assert hasattr(constants, "MAX_VECTOR_DOCS")

    def test_max_vector_docs_value(self):
        """MAX_VECTOR_DOCS doit valoir 5000 (borne de l'index vectoriel)."""
        constants = _reload_constants()
        assert constants.MAX_VECTOR_DOCS == 5000

    def test_max_vector_docs_in_all(self):
        """MAX_VECTOR_DOCS doit apparaitre dans __all__ pour l'import explicite."""
        constants = _reload_constants()
        assert "MAX_VECTOR_DOCS" in constants.__all__

    def test_max_vector_docs_importable_via_all(self):
        """Import via from config.constants import MAX_VECTOR_DOCS doit reussir."""
        constants = _reload_constants()
        # Simule l'import sélectif basé sur __all__
        exported = {name: getattr(constants, name) for name in constants.__all__}
        assert "MAX_VECTOR_DOCS" in exported
        assert exported["MAX_VECTOR_DOCS"] == 5000


class TestCriticalConstantsCompleteness:
    """Vérifie que les constantes critiques de consolidation sont exportées."""

    def test_consolidate_constants_in_all(self):
        """Les constantes CONSOLIDATE_* doivent être dans __all__."""
        constants = _reload_constants()
        consolidate_constants = [
            name for name in constants.__all__
            if name.startswith("CONSOLIDATE_")
        ]
        assert "CONSOLIDATE_DEDUP_SIMILARITY" in consolidate_constants
        assert "CONSOLIDATE_PRUNE_WEIGHT" in consolidate_constants
        assert "CONSOLIDATE_GRACE_HOURS" in consolidate_constants
        assert "CONSOLIDATE_MAX_ITER" in consolidate_constants
