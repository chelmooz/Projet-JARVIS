#!/usr/bin/env python3
"""Contrat `ctx` typé — conformité du contexte applicatif au Protocol (audit P8).

RED : le contexte était passé partout en ``ctx: Any`` (warmup, status) — aucun
contrat vérifiable. Le Protocol ``JarvisContext`` (ports/jarvis_context.py)
déclare les attributs garantis sur le chemin de production ; ce test vérifie
que la vraie classe applicative (``AppContext``) le satisfait réellement
(``isinstance``, donc conformance à l'exécution, pas seulement mypy).
"""

import unittest

from controllers.di import AppContext
from ports.jarvis_context import JarvisContext


class TestContextProtocolConformance(unittest.TestCase):
    """TEST: AppContext satisfait le Protocol JarvisContext."""

    def test_appcontext_satisfies_protocol(self) -> None:
        """RED : le Protocol n'existe pas encore → ImportError attendue."""
        ctx = AppContext()
        self.assertIsInstance(
            ctx,
            JarvisContext,
            "AppContext doit satisfaire JarvisContext (attributs garantis manquants)",
        )

    def test_initialize_member_is_callable(self) -> None:
        """Le membre initialize() fait partie du contrat de cycle de vie."""
        self.assertTrue(callable(getattr(AppContext, "initialize")))


if __name__ == "__main__":
    unittest.main()
