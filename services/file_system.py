"""FileSystemService — Opérations fichiers avec autorisation.

Permissions : seuls les dossiers explicitement autorisés par l'utilisateur
sont lisibles. Rien n'est copié, tout est lu en RAM (max 10 Ko/fichier).
"""
import glob as glob_mod
import logging
import os
import threading
from pathlib import Path

_logger = logging.getLogger("jarvis.file_system")


class FileSystemError(Exception):
    """Erreur contrôlée du service fichier."""


class FileSystemService:
    """Sandbox fichier : autoriser → lister/lire/chercher."""

    def __init__(self):
        self._lock = threading.Lock()
        self._authorized: set[str] = set()

    # ------------------------------------------------------------------
    # Gestion des autorisations
    # ------------------------------------------------------------------

    @staticmethod
    def _is_inside_sandbox(resolved: str) -> bool | None:
        """Check if path is inside JARVIS_FILES_SANDBOX_ROOT. Returns True/False or None if unset."""
        sandbox = os.environ.get('JARVIS_FILES_SANDBOX_ROOT')
        if not sandbox:
            # Sécurité par défaut (Secure by Default) : en production (sans JARVIS_DEV
            # ni pytest), on restreint d'office le sandbox au répertoire du projet
            # pour éviter que JARVIS puisse lire ou lister n'importe quel dossier système.
            import sys

            from config.constants import JARVIS_DEV, PROJECT_DIR
            is_testing = "pytest" in sys.modules
            if JARVIS_DEV or is_testing:
                return None
            sandbox = PROJECT_DIR
        sandbox_resolved = os.path.abspath(sandbox)
        try:
            return Path(resolved).is_relative_to(Path(sandbox_resolved))
        except Exception as e:
            _logger.debug("is_relative_to indisponible, fallback commonpath: %s", e)
            try:
                return os.path.commonpath([resolved, sandbox_resolved]) == sandbox_resolved
            except Exception as e2:
                _logger.debug("commonpath echoue (chemins sur volumes differents?): %s", e2)
                return False

    def authorize_path(self, path: str) -> bool:
        """Authorize path. Returns False if sandbox refuses the path."""
        resolved = os.path.abspath(path)
        if self._is_inside_sandbox(resolved) is False:
            return False
        with self._lock:
            self._authorized.add(resolved)
        return True

    def is_authorized(self, path: str) -> bool:
        """Indique si authorized."""
        resolved = os.path.abspath(path)
        with self._lock:
            return resolved in self._authorized

    def revoke_path(self, path: str) -> bool:
        """Revoke path."""
        resolved = os.path.abspath(path)
        with self._lock:
            if resolved not in self._authorized:
                return False
            self._authorized.discard(resolved)
        return True

    def list_authorized(self) -> list[str]:
        """List authorized."""
        with self._lock:
            return sorted(self._authorized)

    # ------------------------------------------------------------------
    # Contrôle d'accès : vérifie que le chemin (ou un parent) est autorisé
    # ------------------------------------------------------------------

    def _check_authorized(self, path: str) -> str:
        """Vérifie que le chemin (ou un parent direct) est autorisé."""
        resolved = os.path.abspath(path)
        if self._is_inside_sandbox(resolved) is False:
            raise FileSystemError(f"Chemin non authorise (hors sandbox): {resolved}")
        with self._lock:
            if resolved not in self._authorized and not any(Path(resolved).is_relative_to(Path(a)) for a in self._authorized):
                raise FileSystemError(f"Chemin non authorise: {resolved}")
        return resolved

    # ------------------------------------------------------------------
    # Helper — réponse d'erreur structurée avec error_type
    # ------------------------------------------------------------------

    def _error_response(self, msg: str, error_type: str = "unknown") -> dict:
        """Retourne une réponse d'erreur avec type structuré."""
        return {"success": False, "error": msg, "error_type": error_type}

    # ------------------------------------------------------------------
    # list_dir  — scanne un dossier et retourne nom/type/taille
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> dict:
        """List dir."""
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
            entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
            return {"success": True, "path": resolved, "entries": entries}
        except FileSystemError as e:
            return self._error_response(str(e), "not_authorized")
        except OSError as e:
            return self._error_response(str(e), "os_error")

    # ------------------------------------------------------------------
    # read_file  — lit un fichier texte (max 10 Ko, refuse les binaires)
    # ------------------------------------------------------------------

    def read_file(self, path: str) -> dict:
        """Read file."""
        try:
            resolved = os.path.abspath(path)
            parent = os.path.dirname(resolved)
            self._check_authorized(parent)
            if not os.path.isfile(resolved):
                return {"success": False, "error": "Pas un fichier"}
            with open(resolved, encoding="utf-8", errors="strict") as f:
                content = f.read(10001)
            if len(content) > 10000:
                content = content[:10000] + "\n... [tronque a 10 Ko]"
            return {"success": True, "path": resolved, "content": content}
        except FileSystemError as e:
            return self._error_response(str(e), "not_authorized")
        except UnicodeDecodeError as e:
            return self._error_response(str(e), "decode_error")
        except PermissionError:
            return self._error_response("Permission refusee", "permission_denied")
        except OSError as e:
            return self._error_response(str(e), "os_error")

    # ------------------------------------------------------------------
    # find_files  — cherche des fichiers par pattern glob (ex: **/*.log)
    # ------------------------------------------------------------------

    def find_files(self, pattern: str, max_results: int | None = None) -> dict:
        """Find files.

        Borne l'exploration et le nombre de resultats a ``max_results``
        (defaut MAX_FIND_FILES) pour eviter de scanner/retourner des millions
        d'entrees sur une clef USB.
        """
        from config.constants import MAX_FIND_FILES
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
