"""Installateurs Linux pour Ollama.

Extrait de ``services/ollama_installer.py`` (refactor 4.4c) : installateurs
``apt`` (système, non utilisé par le sélecteur portable) et ``tar`` (binaire
portable depuis GitHub).
"""

from __future__ import annotations

import contextlib
import logging
import os
import platform
import shutil
import subprocess
from collections.abc import Callable

from config.constants import LAUNCHER_INSTALL_TIMEOUT, OLLAMA_VERSION
from services.ollama_archive import _extract_tar_zst
from services.ollama_download import _download_file, _verify_ollama_binary
from services.system import BASE_DIR, BIN_LINUX

_logger = logging.getLogger("jarvis.ollama_install_linux")

# Type du callback de log (message, detail, success)
_LogFn = Callable[[str, str, bool | None], None]


def _install_linux_apt(log: _LogFn) -> str | None:
    """Tente d'installer Ollama via apt (Debian/Ubuntu)."""
    try:
        log("Ollama", "Tentative apt install ollama...", None)
        r = subprocess.run(
            ["apt", "install", "-y", "ollama"], capture_output=True, text=True, timeout=LAUNCHER_INSTALL_TIMEOUT
        )
        if r.returncode == 0:
            return shutil.which("ollama")
    except Exception as e:
        log("Ollama", "apt introuvable ou échec", False)
        _logger.debug("Échec apt install ollama : %s", e)
    return None


def _install_linux_tar(log: _LogFn) -> str | None:
    """Télécharge et installe le binaire Linux depuis GitHub."""
    log("Ollama", "Téléchargement binaire Linux...", None)
    arch = platform.machine()
    arch_map = {"x86_64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    ollama_arch = arch_map.get(arch, "amd64")

    url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/ollama-linux-{ollama_arch}.tar.zst"
    cache_dir = os.path.join(BASE_DIR, ".cache")
    os.makedirs(cache_dir, exist_ok=True)

    dl = os.path.join(cache_dir, "ollama-linux.tar.zst")
    dl_bin = os.path.join(cache_dir, "ollama-extract")
    os.makedirs(dl_bin, exist_ok=True)

    result = None
    try:
        _download_file(url, dl, log)
        if not _verify_ollama_binary(dl, f"ollama-linux-{ollama_arch}.tar.zst", log):
            log("Ollama", "Binaire Linux rejeté (SHA256 mismatch)", False)
            return None

        os.makedirs(BIN_LINUX, exist_ok=True)
        _extract_tar_zst(dl, dl_bin, log)

        src = os.path.join(dl_bin, "bin", "ollama")
        if os.path.exists(src):
            dest_bin = os.path.join(BIN_LINUX, "ollama")
            shutil.copy(src, dest_bin)
            os.chmod(dest_bin, 0o755)

        lib_dir = os.path.join(BASE_DIR, "lib", "ollama")
        os.makedirs(lib_dir, exist_ok=True)
        lib_src = os.path.join(dl_bin, "lib", "ollama")

        if os.path.exists(lib_src):
            for entry in os.listdir(lib_src):
                ep = os.path.join(lib_src, entry)
                dp = os.path.join(lib_dir, entry)
                if os.path.isdir(ep):
                    subprocess.run(["cp", "-rL", ep, lib_dir], check=True, timeout=LAUNCHER_INSTALL_TIMEOUT)
                else:
                    shutil.copy2(ep, dp)

        result = os.path.join(BIN_LINUX, "ollama")
    finally:
        if os.path.exists(dl_bin):
            shutil.rmtree(dl_bin, ignore_errors=True)
        if os.path.exists(dl):
            with contextlib.suppress(OSError):
                os.remove(dl)

    return result


__all__ = ["_install_linux_apt", "_install_linux_tar"]
