"""Tests — services.dependency_bootstrap (orchestration provisioning + relance)."""

import logging
import sys
from unittest.mock import patch

from services.dependency_bootstrap import bootstrap_dependencies


class TestBootstrapDependencies:
    def test_same_interpreter_no_pth_patch_no_relaunch(self):
        """Cas nominal : rien à corriger, pas de relance."""
        with (
            patch(
                "services.dependency_bootstrap.ensure_venv",
                return_value=(sys.executable, False),
            ),
            patch("os.execv") as mock_execv,
        ):
            bootstrap_dependencies(logging.getLogger("test"))
            assert not mock_execv.called

    def test_different_interpreter_triggers_relaunch(self):
        """Cas venv distinct de l'interpréteur courant : relance sur le venv."""
        with (
            patch(
                "services.dependency_bootstrap.ensure_venv",
                return_value=("/autre/python", False),
            ),
            patch("os.execv") as mock_execv,
        ):
            bootstrap_dependencies(logging.getLogger("test"))
            assert mock_execv.called
            args = mock_execv.call_args[0]
            assert args[0] == "/autre/python"
            assert args[1][0] == "/autre/python"

    def test_same_interpreter_but_pth_just_patched_triggers_relaunch(self):
        """Cas embeddable Python : même chemin, mais ._pth vient d'être
        corrigé (site-packages activé) -> DOIT relancer quand même, sinon
        les paquets fraîchement installés restent invisibles à l'import
        dans le process courant (._pth n'est relu qu'au démarrage)."""
        with (
            patch(
                "services.dependency_bootstrap.ensure_venv",
                return_value=(sys.executable, True),
            ),
            patch("os.execv") as mock_execv,
        ):
            bootstrap_dependencies(logging.getLogger("test"))
            assert mock_execv.called
            args = mock_execv.call_args[0]
            assert args[0] == sys.executable
