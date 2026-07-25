"""FileSystemService — Opérations fichiers avec autorisation.
Permissions : seuls les dossiers explicitement autorisés par l'utilisateur
sont lisibles. Rien n'est copié, tout est lu en RAM (max 10 Ko/fichier).
"""
from __future__ import annotations
import glob as glob_mod
import logging
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

from config.constants import JARVIS_DEV, MAX_FIND_FILES, PROJECT_DIR

_logger = logging.getLogger("jarvis.file_system")


class FileSystemError(Exception):
    """Erreur contrôlée du service fichier."""
    pass


class FileSystemService:
    """Sandbox fichier : autoriser → lister/lire/chercher."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._authorized: set[str] = set()

    # ------------------------------------------------------------------
    # Gestion des autorisations
    # ------------------------------------------------------------------
    @staticmethod
    def _is_inside_sandbox(resolved: str) -> bool | None:
        """Vérifie si le chemin est dans le sandbox JARVIS_FILES_SANDBOX_ROOT.
        Retourne ``True``/``False``, ou ``None`` si le sandbox n'est pas
        configuré (mode dev/test).
        """
        sandbox = os.environ.get("JARVIS_FILES_SANDBOX_ROOT")
        if not sandbox:
            # Sécurité par défaut (Secure by Default) : en production, on
            # restreint le sandbox au répertoire du projet.
            is_testing = "pytest" in sys.modules
            if JARVIS_DEV or is_testing:
                return None
            sandbox = PROJECT_DIR
        sandbox_resolved = os.path.abspath(sandbox)
        try:
            # Normalisation cross-platform : '\' n'est un séparateur de chemin
            # que sous Windows pour os.path — sur Linux/Mac un payload style
            # '..\..\etc\passwd' reste littéralement un nom de fichier et
            # semble donc "dans" le sandbox. On force la normalisation pour
            # que le contrôle soit identique quel que soit l'OS d'exécution.
            resolved = os.path.abspath(resolved.replace("\\", "/"))
            return Path(resolved).is_relative_to(Path(sandbox_resolved))
        except (AttributeError, ValueError):
            # Fallback pour Python < 3.9 ou chemins sur volumes différents
            try:
                return os.path.commonpath([resolved, sandbox_resolved]) == sandbox_resolved
            except ValueError:
                return False

    def authorize_path(self, path: str) -> bool:
        """Autorise un chemin. Retourne ``False`` si le sandbox le refuse."""
        if not path:
            return False
            
        # Normalisation des séparateurs pour une analyse cohérente