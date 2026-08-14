"""Extraction d'archives — tar.zst et zip (portable, sûr).

Extrait de services/ollama_installer.py (refactor Lot 4.4b).
Responsabilités :
  - ``_extract_tar_zst`` : extraction .tar.zst avec fallback sans zstd externe
  - ``_safe_extract_zip`` : extraction .zip refusant toute sortie du répertoire
    cible (path traversal / liens symboliques)

Les imports restent volontairement minimaux. ``_LogFn`` est le même type
callback de log que services/ollama_installer.py / services/ollama_download.py
(convention du dépôt : alias par module, pas de module partagé).
"""

from __future__ import annotations

import logging
import os
import stat
import subprocess
import zipfile
from collections.abc import Callable

from config.constants import LAUNCHER_WAIT_TIMEOUT

_logger = logging.getLogger(__name__)

# Type du callback de log (message, detail, success)
_LogFn = Callable[[str, str, bool | None], None]


def _extract_tar_zst(archive: str, dest_dir: str, log: _LogFn) -> None:
    """Extrait une archive .tar.zst.

    `tar --zstd` nécessite le binaire externe `zstd`, absent sur une Debian/
    Ubuntu minimale (clé USB bootable). Si l'option échoue faute de binaire,
    on retombe sur `tar -xf` : les `tar` récents (libarchive/liblzma) savent
    souvent auto-détecter zstd sans dépendance externe.
    """
    try:
        subprocess.run(["tar", "--zstd", "xf", archive, "-C", dest_dir], check=True, timeout=LAUNCHER_WAIT_TIMEOUT)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        log("Ollama", "tar --zstd indisponible (binaire zstd manquant ?), fallback tar -xf", False)
        _logger.debug("Échec tar --zstd : %s", e)
        subprocess.run(["tar", "-xf", archive, "-C", dest_dir], check=True, timeout=LAUNCHER_WAIT_TIMEOUT)


def _safe_extract_zip(archive: str, dest_dir: str) -> None:
    """Extrait une archive ZIP sans autoriser de sortie du répertoire cible.

    Les archives ZIP malveillantes peuvent contenir des chemins ``../`` ou des
    liens symboliques. Ces entrées sont refusées avant toute écriture pour
    préserver le support portable et le poste hôte.
    """
    destination = os.path.realpath(dest_dir)
    with zipfile.ZipFile(archive, "r") as zf:
        for entry in zf.infolist():
            target = os.path.realpath(os.path.join(destination, entry.filename))
            try:
                is_within_destination = os.path.commonpath([destination, target]) == destination
            except ValueError:
                is_within_destination = False
            is_symlink = stat.S_ISLNK(entry.external_attr >> 16)
            if not is_within_destination or is_symlink:
                raise ValueError(f"Entrée ZIP non sûre refusée : {entry.filename}")
        zf.extractall(destination)
