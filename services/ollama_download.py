"""Téléchargement et vérification d'intégrité pour Ollama.

Extrait de services/ollama_installer.py (refactor Lot 4.4).
Responsabilités :
  - Téléchargement atomique (_download_file)
  - Vérification SHA256 (_sha256_of, _expected_ollama_sha256, _verify_ollama_binary)
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import urllib.request
from collections.abc import Callable

from config.constants import LAUNCHER_DOWNLOAD_TIMEOUT, OLLAMA_VERSION

_logger = logging.getLogger("jarvis.ollama_download")

# Type du callback de log (message, detail, success)
_LogFn = Callable[[str, str, bool | None], None]


def _download_file(url: str, dest: str, log: _LogFn, timeout: int = LAUNCHER_DOWNLOAD_TIMEOUT) -> None:
    """Télécharge un fichier de manière atomique (.part puis rename)."""
    dest_dir = os.path.dirname(os.path.abspath(dest))
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    part = f"{dest}.part"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, open(part, "wb") as f:
            while True:
                block = resp.read(1 << 20)  # 1 Mo
                if not block:
                    break
                f.write(block)
        os.replace(part, dest)
    except Exception:
        if os.path.exists(part):
            with contextlib.suppress(OSError):
                os.remove(part)
        raise


def _sha256_of(path: str) -> str:
    """Calcule le hash SHA256 d'un fichier par blocs (mémoire constante)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _expected_ollama_sha256(asset_name: str, log: _LogFn) -> str | None:
    """Récupère le hash SHA256 attendu depuis les releases GitHub."""
    try:
        url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/sha256sum.txt"
        with urllib.request.urlopen(url, timeout=LAUNCHER_DOWNLOAD_TIMEOUT) as r:
            content = r.read().decode("utf-8", "ignore")
        for line in content.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].strip("*").removeprefix("./") == asset_name:
                return str(parts[0].lower())
    except Exception as e:
        _logger.debug("SHA256 Ollama indisponible (offline ?) : %s", e)
        log("Ollama", "Vérification SHA256 sautée (source de hash indisponible)", False)
    return None


def _verify_ollama_binary(path: str, asset_name: str, log: _LogFn) -> bool:
    """Vérifie l'intégrité SHA256 du binaire téléchargé."""
    expected = _expected_ollama_sha256(asset_name, log)
    if expected is None:
        # Un téléchargement ne doit jamais être accepté sans empreinte attendue.
        # Cette fonction n'est appelée qu'après un accès réseau : l'absence du
        # manifeste de sommes de contrôle est donc un échec de sécurité, pas un
        # cas d'usage hors ligne.
        log("Ollama", "Installation refusée : SHA256 attendu indisponible", False)
        return False

    actual = _sha256_of(path).lower()
    if actual != expected:
        log("Ollama", f"SHA256 MISMATCH : attendu {expected}, obtenu {actual}", False)
        return False

    log("Ollama", "Intégrité SHA256 vérifiée", True)
    return True


__all__ = [
    "_download_file",
    "_sha256_of",
    "_expected_ollama_sha256",
    "_verify_ollama_binary",
]
