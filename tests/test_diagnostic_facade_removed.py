#!/usr/bin/env python3
"""Verrou de non-régression : ``services/diagnostic.py`` reste supprimé (audit P11).

La façade de compatibilité ne redirigeait que vers ``services/diagnostics/
service.py`` — plus aucun import direct (production ni tests) depuis la
migration. Le package ``services/diagnostics/`` (checks/rules/report/service)
est la source de vérité unique : ``service.py`` délègue aux feuilles
``checks.py`` sans duplication.
"""

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FACADE_MODULE = PROJECT_ROOT / "services" / "diagnostic.py"
SCAN_DIRS = (
    "config",
    "controllers",
    "services",
    "agents",
    "graph",
    "ports",
    "models",
    "scripts",
    "tests",
)
LEGACY_MODULE = "services.diagnostic"


def _is_legacy_module(name: str) -> bool:
    """Vrai pour ``services.diagnostic`` (et sous-modules), faux pour
    ``services.diagnostics`` (package réel) et ``services.diagnostic_ext``."""
    return name == LEGACY_MODULE or name.startswith(LEGACY_MODULE + ".")


class TestNoDiagnosticFacade(unittest.TestCase):
    """TEST: la façade services/diagnostic.py n'existe plus et n'est importée nulle part."""

    def test_facade_module_does_not_exist(self) -> None:
        """RED (P11) : le fichier existe encore → échec attendu."""
        self.assertFalse(
            FACADE_MODULE.exists(),
            "services/diagnostic.py est une façade morte (0 import). "
            "Supprimer le fichier — services/diagnostics/service.py est la cible.",
        )

    def test_no_import_of_legacy_facade_anywhere(self) -> None:
        """Verrou : si la façade revient, elle doit être réellement branchée."""
        offenders: list[str] = []
        for directory in SCAN_DIRS:
            root = PROJECT_ROOT / directory
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                if any(part in {"__pycache__", ".venv", "build"} for part in path.parts):
                    continue
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module is not None:
                        if _is_legacy_module(node.module):
                            offenders.append(f"{path}: from {node.module} import ...")
                    elif isinstance(node, ast.Import) and any(_is_legacy_module(alias.name) for alias in node.names):
                        offenders.append(f"{path}: import {node.names[0].name}")
        self.assertEqual(
            offenders,
            [],
            f"Imports de services.diagnostic (façade) détectés : {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
