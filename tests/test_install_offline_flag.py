#!/usr/bin/env python3
"""Verrou de comportement pour le bootstrap offline (audit P3, précision contre-audit).

RED : sous ``JARVIS_OFFLINE=1`` sans ``vendor_wheels/``, ``install_python_deps()``
tentait quand même ``pip install`` vers PyPI — fallback silencieux et
inconditionnel. Contrat attendu :
1. flag posé + pas de wheels locales → refus explicite (message clair),
   retour ``False``, **zéro** appel subprocess (jamais de réseau) ;
2. sans flag → comportement actuel préservé (fallback PyPI) et épinglé ici.
"""

import contextlib
import io
import os
import unittest
from unittest.mock import MagicMock, patch

import scripts.install as install


class TestInstallOfflineFlag(unittest.TestCase):
    """TEST: le flag JARVIS_OFFLINE refuse le fallback PyPI sans wheels locales."""

    def test_offline_flag_refuses_without_vendor_wheels(self) -> None:
        """RED : JARVIS_OFFLINE=1 + aucun vendor_wheels → False, zéro appel pip."""
        pip_calls: list[list[str]] = []

        with (
            patch.dict(os.environ, {"JARVIS_OFFLINE": "1"}, clear=False),
            patch("scripts.install._vendor_find_links", return_value=[]),
            patch(
                "scripts.install.subprocess.run",
                side_effect=lambda *args, **kwargs: pip_calls.append(args),
            ),
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = install.install_python_deps()

        self.assertIs(result, False, "Le refus offline doit retourner False")
        self.assertEqual(
            pip_calls,
            [],
            "Offline sans wheels locales : aucun appel pip ne doit être tenté",
        )
        out = stdout.getvalue()
        self.assertIn("JARVIS_OFFLINE", out, "Le message doit citer le flag")
        self.assertIn("vendor_wheels", out, "Le message doit orienter vers vendor_wheels/")

    def test_without_flag_pypi_fallback_preserved(self) -> None:
        """Pin : sans flag, le fallback PyPI actuel reste intact (2 appels pip)."""
        pip_calls: list[list[str]] = []
        ok = MagicMock(returncode=0)

        with (
            patch.dict(os.environ, {"JARVIS_OFFLINE": ""}, clear=False),
            patch("scripts.install._vendor_find_links", return_value=[]),
            patch(
                "scripts.install.subprocess.run",
                side_effect=lambda *args, **kwargs: (pip_calls.append(args), ok)[1],
            ),
        ):
            result = install.install_python_deps()

        self.assertIs(result, True)
        self.assertEqual(len(pip_calls), 2, "upgrade pip/setuptools + install .")
        self.assertEqual(pip_calls[1][0][-1], ".", "Le dernier appel doit être pip install .")


if __name__ == "__main__":
    unittest.main()
