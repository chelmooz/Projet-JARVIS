#!/usr/bin/env python3
"""Verrou de non-régression : ``services/facts.py`` reste supprimé (audit P12).

``FactStore`` était orphelin : zéro import/usage ailleurs dans le repo (ni
production, ni tests). Aucun remplacement — le module n'était jamais instancié.
Ce test interdit :
1. la réapparition du fichier ;
2. son import silencieux depuis n'importe quel module source ou test.
"""

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FACTS_MODULE = PROJECT_ROOT / "services" / "facts.py"
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


class TestNoOrphanFactsModule(unittest.TestCase):
    """TEST: services/facts.py n'existe plus et n'est importé nulle part."""

    def test_facts_module_does_not_exist(self) -> None:
        """RED (P12) : le fichier existe encore → échec attendu."""
        self.assertFalse(
            FACTS_MODULE.exists(),
            "services/facts.py est du code mort (0 référence hors lui-même). Supprimer le fichier.",
        )

    def test_no_import_of_facts_module_anywhere(self) -> None:
        """Verrou : si facts.py revient, il doit être réellement branché."""
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
                    if (
                        isinstance(node, ast.ImportFrom)
                        and node.module is not None
                        and "facts" in node.module.split(".")
                    ):
                        offenders.append(f"{path}: from {node.module} import ...")
                    elif isinstance(node, ast.Import) and any("facts" in alias.name.split(".") for alias in node.names):
                        offenders.append(f"{path}: import {node.names[0].name}")
        self.assertEqual(
            offenders,
            [],
            f"Imports de services.facts détectés : {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
