"""OllamaInstaller — Installation du binaire Ollama.

Extrait de services/launcher.py (refactor Q4).
Responsabilités :
  - Sélecteur de plateforme (installateurs extraits 4.4c)
  - Point d'entrée unique ensure_ollama_binary
  - Délègue téléchargement et vérification SHA256 à services.ollama_download
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
from collections.abc import Callable

from config.constants import LAUNCHER_WAIT_TIMEOUT, OLLAMA_VERSION
from services.ollama_archive import _extract_tar_zst, _safe_extract_zip
from services.ollama_download import (
    _download_file,
    _verify_ollama_binary,
)
from services.ollama_install_linux import _install_linux_apt, _install_linux_tar
from services.system import BASE_DIR, BIN_DIR, SYSTEM, get_ollama_path

_logger = logging.getLogger("jarvis.ollama_installer")

# Type du callback de log (message, detail, success)
_LogFn = Callable[[str, str, bool | None], None]


def _install_windows_zip(log: _LogFn) -> str | None:
    """Télécharge et installe le binaire Windows depuis GitHub."""
    log("Ollama", "Téléchargement binaire Windows...", None)
    temp = os.environ.get("TEMP", "/tmp")
    url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-windows-amd64.zip"
    dl = os.path.join(temp, "ollama-windows.zip")
    dl_bin = os.path.join(temp, "ollama-extract")
    os.makedirs(dl_bin, exist_ok=True)

    try:
        _download_file(url, dl, log)
        if not _verify_ollama_binary(dl, "ollama-windows-amd64.zip", log):
            log("Ollama", "Archive Windows rejetée (SHA256 mismatch)", False)
            return None

        os.makedirs(BIN_DIR, exist_ok=True)
        _safe_extract_zip(dl, dl_bin)

        src = os.path.join(dl_bin, "ollama.exe")
        if os.path.exists(src):
            shutil.copy(src, os.path.join(BIN_DIR, "ollama.exe"))

        # CORRECTION : l'archive Windows contient aussi lib/ollama/ (llama-server.exe,
        # DLL GPU) — sans cette copie, ollama.exe démarre mais ne trouve jamais le
        # moteur d'inférence ("failure during llama-server GPU discovery"). On
        # reproduit ici la même logique que _install_linux_tar (lib/ollama copié
        # sous BASE_DIR/lib/ollama, un des chemins qu'Ollama sonde nativement).
        lib_src = os.path.join(dl_bin, "lib", "ollama")
        if os.path.exists(lib_src):
            lib_dest = os.path.join(BASE_DIR, "lib", "ollama")
            # Etape silencieuse sinon (aucun log() pendant shutil.copytree) — sur
            # cle USB (I/O lente, fichiers un par un) cela ressemble a un gel.
            log("Ollama", f"Copie du moteur d'inference ({lib_src} -> {lib_dest})...", None)
            shutil.copytree(lib_src, lib_dest, dirs_exist_ok=True)
            log("Ollama", "Moteur d'inference copie", True)

        return os.path.join(BIN_DIR, "ollama.exe")
    finally:
        if os.path.exists(dl):
            with contextlib.suppress(OSError):
                os.remove(dl)
        if os.path.exists(dl_bin):
            shutil.rmtree(dl_bin, ignore_errors=True)


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
    "_install_linux_apt",
    "_install_linux_tar",
]
