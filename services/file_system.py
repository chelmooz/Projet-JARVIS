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
from config.paths import IS_WINDOWS

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
        # (cast str() : PROJECT_DIR et consorts peuvent arriver en Path,
        # or Path.replace() est l'API de renommage de fichier, pas str.replace)
        path = str(path)
        normalized_path = path.replace("\\", "/")

        # Cas A : Rejet défensif des chemins absolus Windows (ex: "C:\...")
        # quand on tourne SUR Linux/macOS. Sur ces OS, ':' n'a aucun sens
        # de séparateur pour os.path : "C:\Users\x" est traité comme un nom
        # de fichier relatif littéral, ce qui peut créer un faux-négatif de
        # sandboxing. Sur Windows natif, à l'inverse, le lecteur fait partie
        # de TOUT chemin absolu légitime (y compris PROJECT_DIR lui-même) :
        # ce garde-fou ne doit donc s'appliquer que hors Windows.
        if not IS_WINDOWS and re.match(r'^[A-Za-z]:', normalized_path):
            _logger.warning("Tentative de path traversal bloquée (lecteur Windows) : %s", path)
            return False

        # Cas B : Rejet défensif de TOUTE tentative contenant ".." en substring
        # Neutralise les contournements de filtres naïfs (ex: "....//....//")
        if ".." in normalized_path:
            _logger.warning("Tentative de path traversal bloquée (séquence ..) : %s", path)
            return False

        resolved = os.path.abspath(path)
        if self._is_inside_sandbox(resolved) is False:
            return False
        with self._lock:
            self._authorized.add(resolved)
        return True

    def is_authorized(self, path: str) -> bool:
        """Indique si un chemin est autorisé."""
        resolved = os.path.abspath(path)
        with self._lock:
            return resolved in self._authorized

    def revoke_path(self, path: str) -> bool:
        """Révoque l'autorisation d'un chemin."""
        resolved = os.path.abspath(path)
        with self._lock:
            if resolved not in self._authorized:
                return False
            self._authorized.discard(resolved)
        return True

    def list_authorized(self) -> list[str]:
        """Liste les chemins autorisés (triés)."""
        with self._lock:
            return sorted(self._authorized)

    # ------------------------------------------------------------------
    # Contrôle d'accès : vérifie que le chemin (ou un parent) est autorisé
    # ------------------------------------------------------------------
    def _check_authorized(self, path: str) -> str:
        """Vérifie que le chemin (ou un parent direct) est autorisé.
        Retourne le chemin résolu. Lève ``FileSystemError`` si non autorisé.
        """
        resolved = os.path.abspath(path)
        if self._is_inside_sandbox(resolved) is False:
            raise FileSystemError(f"Chemin non autorisé (hors sandbox) : {resolved}")
        with self._lock:
            is_allowed = resolved in self._authorized or any(
                Path(resolved).is_relative_to(Path(a)) for a in self._authorized
            )
            if not is_allowed:
                raise FileSystemError(f"Chemin non autorisé : {resolved}")
        return resolved

    # ------------------------------------------------------------------
    # Helper — réponse d'erreur structurée avec error_type
    # ------------------------------------------------------------------
    @staticmethod
    def _error_response(msg: str, error_type: str = "unknown") -> dict[str, Any]:
        """Retourne une réponse d'erreur avec type structuré."""
        return {"success": False, "error": msg, "error_type": error_type}

    # ------------------------------------------------------------------
    # list_dir  — scanne un dossier et retourne nom/type/taille
    # ------------------------------------------------------------------
    def list_dir(self, path: str) -> dict[str, Any]:
        """Liste le contenu d'un dossier autorisé."""
        try:
            resolved = self._check_authorized(path)
            entries = []
            for entry in os.scandir(resolved):
                entries.append({
                    "name": entry.name,
                    "path": entry.path,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else 0,
                })
            # Tri : dossiers d'abord, puis par nom (insensible à la casse)
            entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
            return {"success": True, "path": resolved, "entries": entries}
        except FileSystemError as e:
            return self._error_response(str(e), "not_authorized")
        except OSError as e:
            return self._error_response(str(e), "os_error")

    # ------------------------------------------------------------------
    # read_file  — lit un fichier texte (max 10 Ko, refuse les binaires)
    # ------------------------------------------------------------------
    def read_file(self, path: str) -> dict[str, Any]:
        """Lit un fichier texte autorisé (max 10 Ko)."""
        try:
            resolved = os.path.abspath(path)
            parent = os.path.dirname(resolved)
            self._check_authorized(parent)
            if not os.path.isfile(resolved):
                return {"success": False, "error": "Pas un fichier"}
            with open(resolved, encoding="utf-8", errors="strict") as f:
                content = f.read(10001)
            if len(content) > 10000:
                content = content[:10000] + "\n... [tronqué à 10 Ko]"
            return {"success": True, "path": resolved, "content": content}
        except FileSystemError as e:
            return self._error_response(str(e), "not_authorized")
        except UnicodeDecodeError as e:
            return self._error_response(str(e), "decode_error")
        except PermissionError:
            return self._error_response("Permission refusée", "permission_denied")
        except OSError as e:
            return self._error_response(str(e), "os_error")

    # ------------------------------------------------------------------
    # find_files  — cherche des fichiers par pattern glob (ex: **/*.log)
    # ------------------------------------------------------------------
    def find_files(self, pattern: str, max_results: int | None = None) -> dict[str, Any]:
        """Cherche des fichiers par pattern glob (ex: ``**/*.log``).
        Borne l'exploration et le nombre de résultats à ``max_results``
        (défaut ``MAX_FIND_FILES``) pour éviter de scanner/retourner des
        millions d'entrées sur une clef USB.
        """
        if max_results is None:
            max_results = MAX_FIND_FILES
        try:
            resolved = os.path.abspath(os.path.dirname(pattern))
            self._check_authorized(resolved)
            matches: list[str] = []
            for match in glob_mod.iglob(pattern, recursive=True):
                matches.append(match)
                if len(matches) >= max_results:
                    break
            return {
                "success": True,
                "pattern": pattern,
                "matches": sorted(matches),
                "truncated": len(matches) >= max_results,
            }
        except FileSystemError as e:
            return self._error_response(str(e), "not_authorized")
        except OSError as e:
            return self._error_response(str(e), "os_error")


__all__ = ["FileSystemError", "FileSystemService"]
