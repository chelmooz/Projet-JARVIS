"""Installateur Windows pour Ollama.

Extrait de ``services/ollama_installer.py`` (refactor 4.4c) : installateur
``zip`` portable depuis GitHub (binaire + moteur d'inférence ``lib/ollama``).
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
from collections.abc import Callable

from config.constants import OLLAMA_VERSION
from services.ollama_archive import _safe_extract_zip
from services.ollama_download import _download_file, _verify_ollama_binary
from services.system import BASE_DIR, BIN_DIR

_logger = logging.getLogger("jarvis.ollama_install_windows")

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


__all__ = ["_install_windows_zip"]
