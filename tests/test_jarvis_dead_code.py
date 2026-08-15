#!/usr/bin/env python3
"""Verrou de non-régression : aucune fonction privée morte dans jarvis.py.

Lot 1 (audit P7) : ``_shutdown`` était définie (l.70) mais jamais enregistrée
via ``signal.signal`` ni appelée nulle part — code mort. Uvicorn gère
nativement SIGINT/SIGTERM (docstring jarvis.py) et le ``finally: pm.stop_all()``
couvre l'arrêt d'Ollama ; sur Windows, ``services/launcher_win.py`` enregistre
son propre handler. Le handler de ``jarvis.py`` a donc été supprimé : ce test
interdit le retour de toute fonction privée orpheline.
"""

import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
JARVIS_SOURCE = PROJECT_ROOT / "jarvis.py"


class TestJarvisNoDeadCode(unittest.TestCase):
    """TEST: toute fonction privée de jarvis.py est référencée au moins une fois."""

    @staticmethod
    def _module_private_functions(tree: ast.Module) -> list[ast.FunctionDef]:
        """Fonctions privées (préfixe `_`) définies au niveau module."""
        return [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_")
        ]

    @staticmethod
    def _referenced_names(tree: ast.Module) -> set[str]:
        """Noms chargés (lectures) partout dans le module, y compris les appels."""
        return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}

    def test_jarvis_py_has_no_dead_private_function(self):
        """RED (Lot 1/P7) : `_shutdown` définie mais jamais référencée → échec attendu."""
        tree = ast.parse(JARVIS_SOURCE.read_text(encoding="utf-8"))
        referenced = self._referenced_names(tree)
        dead = [node.name for node in self._module_private_functions(tree) if node.name not in referenced]
        self.assertEqual(
            dead,
            [],
            "Fonction(s) privée(s) morte(s) dans jarvis.py : "
            f"{', '.join(dead)} — définie(s) mais jamais enregistrée(s) ni "
            "appelée(s). Supprimer ou enregistrer via signal.signal.",
        )


if __name__ == "__main__":
    unittest.main()
