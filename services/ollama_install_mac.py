"""Installateurs macOS pour Ollama.

Extrait de ``services/ollama_installer.py`` (refactor 4.4c) :
- Homebrew (si présent)
- Refus du script distant (curl | sh) — politique portable
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable

from config.constants import LAUNCHER_WAIT_TIMEOUT

_logger = logging.getLogger("jarvis.ollama_install_mac")

# Type du callback de log (message, detail, success)
_LogFn = Callable[[str, str, bool | None], None]


def _install_mac_brew(log: _LogFn) -> str | None:
    """Tente d'installer Ollama via Homebrew (macOS)."""
    if not shutil.which("brew"):
        return None
    try:
        log("Ollama", "Installation via brew...", None)
        subprocess.run(["brew", "install", "ollama"], capture_output=True, timeout=LAUNCHER_WAIT_TIMEOUT)
        return shutil.which("ollama")
    except Exception as e:
        log("Ollama", f"Échec brew : {e}", False)
    return None


def _install_mac_script(log: _LogFn) -> str | None:
    """Refuse l'exécution automatique d'un script distant sur macOS.

    Le produit promet une exécution portable qui ne modifie pas le poste hôte.
    Exécuter ``curl | sh`` contredit cette promesse et ne permet pas de vérifier
    l'intégrité de ce qui est exécuté. L'utilisateur doit installer Ollama par
    le canal officiel de son choix, puis relancer JARVIS.
    """
    log(
        "Ollama",
        "Installation macOS automatique désactivée : aucun script réseau n'est exécuté.",
        False,
    )
    return None


__all__ = ["_install_mac_brew", "_install_mac_script"]
