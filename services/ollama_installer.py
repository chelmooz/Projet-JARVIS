"""OllamaInstaller — Installation du binaire Ollama.

Extrait de services/launcher.py (refactor Q4).
Responsabilités :
  - Sélecteur de plateforme (installateurs extraits 4.4c)
  - Point d'entrée unique ensure_ollama_binary
  - Délègue téléchargement et vérification SHA256 à services.ollama_download
"""

from __future__ import annotations

import logging
import shutil  # noqa: F401 (patche dans tests via services.ollama_installer.shutil)
import subprocess
from collections.abc import Callable

from services.ollama_archive import _extract_tar_zst, _safe_extract_zip
from services.ollama_download import _verify_ollama_binary
from services.ollama_install_linux import _install_linux_apt, _install_linux_tar
from services.ollama_install_mac import _install_mac_brew, _install_mac_script
from services.ollama_install_windows import _install_windows_zip
from services.system import SYSTEM, get_ollama_path

_logger = logging.getLogger("jarvis.ollama_installer")

# Type du callback de log (message, detail, success)
_LogFn = Callable[[str, str, bool | None], None]


def _is_real_ollama(path: str) -> bool:
    """Vérifie que le binaire est bien Ollama et pas un faux positif."""
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
        return "ollama" in r.stdout.lower() or "ollama" in r.stderr.lower()
    except Exception as e:
        _logger.warning("Vérification binaire Ollama échouée (%s) : %s", path, e)
        return False


def ensure_ollama_binary(log: _LogFn) -> str | None:
    """Point d'entrée unique : vérifie ou installe le binaire Ollama."""
    existing = get_ollama_path()
    if existing:
        if not _is_real_ollama(existing):
            log("Ollama", f"Binaire suspect ou corrompu : {existing}", False)
            return None
        return existing

    log("Ollama", "Binaire introuvable, tentative d'installation...", None)
    installers = {
        # JARVIS reste portable : aucune installation système (apt, brew ou
        # script distant) n'est lancée automatiquement sur le poste hôte.
        "linux": [_install_linux_tar],
        "darwin": [_install_mac_script],
        "windows": [_install_windows_zip],
    }

    for install_fn in installers.get(SYSTEM, []):
        try:
            result = install_fn(log)
            if result:
                return result
        except Exception as e:
            log("Ollama", f"Échec {install_fn.__name__} : {e}", False)

    if SYSTEM == "windows":
        log("Ollama", "Téléchargez manuellement depuis https://ollama.com/download/windows", False)

    return None


# Ré-export volontaire : les tests (test_ollama_installer.py,
# test_ollama_installer_security.py) accèdent aux fonctions d'extraction via
# services.ollama_installer — ce ré-export doit rester valide.
__all__ = [
    "ensure_ollama_binary",
    "_extract_tar_zst",
    "_safe_extract_zip",
    "_verify_ollama_binary",
    "_install_linux_apt",
    "_install_linux_tar",
    "_install_mac_brew",
    "_install_mac_script",
    "_install_windows_zip",
]
