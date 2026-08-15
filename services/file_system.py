"""FileSystemService — Opérations fichiers avec autorisation.
Permissions : seuls les dossiers explicitement autorisés par l'utilisateur
sont lisibles. Rien n'est copié, tout est lu en RAM (max 10 Ko/fichier).
"""

from __future__ import annotations

import glob as glob_mod
import json
import logging
import os
import re
import threading
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from config.constants import MAX_FIND_FILES
from config.paths import FILE_AUTHORIZED_PATHS, IS_WINDOWS

_logger = logging.getLogger("jarvis.file_system")


class FileSystemError(Exception):
    """Erreur contrôlée du service fichier."""

    pass


class FileSystemService:
    """Sandbox fichier : autoriser -> lister/lire/chercher."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._lock = threading.Lock()
        self._authorized: set[Path] = set()
        if config_path is None:
            self._config_path = FILE_AUTHORIZED_PATHS
        else:
            self._config_path = Path(config_path)
        self._load_authorized()

    def _load_authorized(self) -> None:
        """Charge les chemins autorisés depuis le fichier de config."""
        if self._config_path.exists():
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    with self._lock:
                        self._authorized = {Path(self._resolve_real_path(p)) for p in data}
                    _logger.info(
                        "Chemins autorisés chargés depuis %s (%d entrées)", self._config_path, len(self._authorized)
                    )
            except (json.JSONDecodeError, OSError) as e:
                _logger.warning("Impossible de charger %s : %s", self._config_path, e)

    def _save_authorized(self) -> None:
        """Sauvegarde les chemins autorisés dans le fichier de config."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                paths = sorted(str(p) for p in self._authorized)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(paths, f, ensure_ascii=False, indent=2)
        except OSError as e:
            _logger.error("Impossible de sauvegarder %s : %s", self._config_path, e)

    # ------------------------------------------------------------------
    # Gestion des autorisations
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_real_path(path: str | Path) -> str:
        """Résout un chemin en suivant les liens symboliques et en normalisant
        les séparateurs de chemin pour une comparaison cohérente cross-platform.

        Utilise PureWindowsPath/PurePosixPath selon la plateforme pour éviter
        la transformation destructrice d'un backslash littéral dans un nom de
        fichier sous Linux (ex: "test\\file.txt" -> "test/file.txt" incorrect).

        Sur Windows, on conserve le remplacement \\ -> / pour compatibilité
        avec os.path.realpath qui fonctionne mieux avec des slashes forward.

        Args:
            path: Chemin à résoudre (string ou Path object)

        Returns:
            Chemin réel avec séparateurs normalisés
        """
        path_str = str(path)
        pure: PureWindowsPath | PurePosixPath
        if IS_WINDOWS:
            # Sur Windows : parser avec PureWindowsPath, puis normaliser avec slashes forward
            # pour compatibilité os.path.realpath
            pure = PureWindowsPath(path_str)
            resolved = os.path.realpath(str(pure).replace("\\", "/"))
        else:
            # Sur Linux/macOS : parser avec PurePosixPath (garde les \ littéraux)
            pure = PurePosixPath(path_str)
            resolved = os.path.realpath(str(pure))
        return resolved

    def _default_roots(self) -> list[str]:
        """Aucune racine configurée : fail-closed conservé (ADR-011).

        Comportement historique inchangé : sans ``JARVIS_FILES_SANDBOX_ROOT``,
        toute opération est refusée avec le message dédié (aucune autorisation
        possible).
        """
        raise FileSystemError("Sandbox non configuré : définissez JARVIS_FILES_SANDBOX_ROOT")

    def _sandbox_roots(self) -> list[str]:
        """Résout les racines autorisées (multi-périmètres ou wildcard)."""
        raw = os.environ.get("JARVIS_FILES_SANDBOX_ROOT", "").strip()

        # Wildcard : tous les lecteurs montés, résolus dynamiquement
        if raw == "*":
            try:
                import psutil

                roots = [p.mountpoint for p in psutil.disk_partitions(all=False) if p.mountpoint]
            except Exception:
                roots = []
            return [os.path.normpath(r) for r in roots] if roots else self._default_roots()

        # Multi-périmètres séparés par os.pathsep (';' Windows, ':' Linux)
        if raw:
            parts = [p.strip() for p in raw.split(os.pathsep) if p.strip()]
            return [os.path.normpath(p) for p in parts]

        return self._default_roots()  # comportement actuel inchangé si variable absente

    def _within_sandbox(self, path: str) -> bool:
        p = os.path.normpath(path)
        for root in self._sandbox_roots():
            try:
                if os.path.commonpath([p, root]) == root:
                    return True
            except ValueError:
                continue  # lecteurs différents (C: vs D:)
        return False

    def authorize_path(self, path: str) -> bool:
        """Autorise un chemin. Retourne ``False`` si le sandbox le refuse."""
        ok, _ = self.authorize_path_verbose(path)
        return ok

    def authorize_path_verbose(self, path: str) -> tuple[bool, str | None]:
        """Autorise un chemin, avec le motif de refus le cas échéant.

        Source unique de la logique d'autorisation : ``authorize_path`` (utilisé
        par kill_coding.py / code_review.py) délègue ici et ignore le motif ;
        la route API (``/api/files/authorize``) l'utilise pour renvoyer une
        erreur exploitable côté UI plutôt qu'un "inconnue" générique.
        """
        if not path:
            return False, "Chemin vide"

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
        if not IS_WINDOWS and re.match(r"^[A-Za-z]:", normalized_path):
            _logger.warning("Tentative de path traversal bloquée (lecteur Windows) : %s", path)
            return False, "Chemin Windows refusé sur cette plateforme"

        # Cas B : Rejet défensif de TOUTE tentative contenant ".." en substring
        # Neutralise les contournements de filtres naïfs (ex: "....//....//")
        if ".." in normalized_path:
            _logger.warning("Tentative de path traversal bloquée (séquence ..) : %s", path)
            return False, "Séquence '..' interdite"

        resolved = self._resolve_real_path(path)
        try:
            if self._within_sandbox(resolved) is False:
                return False, f"Hors du périmètre autorisé (JARVIS_FILES_SANDBOX_ROOT) : {resolved}"
        except FileSystemError as e:
            _logger.warning("Autorisation refusée : %s", e)
            return False, str(e)

        with self._lock:
            self._authorized.add(Path(resolved))
        self._save_authorized()
        return True, None

    def is_authorized(self, path: str) -> bool:
        """Indique si un chemin est autorisé."""
        resolved = self._resolve_real_path(path)
        with self._lock:
            return Path(resolved) in self._authorized

    def revoke_path(self, path: str) -> bool:
        """Révoque l'autorisation d'un chemin."""
        resolved = self._resolve_real_path(path)
        with self._lock:
            if Path(resolved) not in self._authorized:
                return False
            self._authorized.discard(Path(resolved))
        self._save_authorized()
        return True

    def list_authorized(self) -> list[str]:
        """Liste les chemins autorisés (triés)."""
        with self._lock:
            return sorted(str(p) for p in self._authorized)

    # ------------------------------------------------------------------
    # Contrôle d'accès : vérifie que le chemin (ou un parent) est autorisé
    # ------------------------------------------------------------------
    def _check_authorized(self, path: str) -> str:
        """Vérifie que le chemin (ou un parent direct) est autorisé.
        Retourne le chemin résolu. Lève ``FileSystemError`` si non autorisé.
        """
        resolved = self._resolve_real_path(path)
        if self._within_sandbox(resolved) is False:
            raise FileSystemError(f"Chemin non autorisé (hors sandbox) : {resolved}")
        resolved_path = Path(resolved)
        with self._lock:
            is_allowed = resolved_path in self._authorized or any(
                resolved_path.is_relative_to(a) for a in self._authorized
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
            entries: list[dict[str, Any]] = []
            for entry in os.scandir(resolved):
                entries.append(
                    {
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": entry.is_dir(),
                        "size": entry.stat().st_size if entry.is_file() else 0,
                    }
                )
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
            resolved = self._resolve_real_path(path)
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
    @staticmethod
    def _contains_path_traversal(pattern: str) -> bool:
        """Détecte une tentative d'évasion de sandbox dans un pattern glob
        (composant ``..``). Le check sur ``dirname(pattern)`` ne suffit pas :
        glob() résout ``**`` à zéro répertoire, ce qui permet à un pattern
        ``AUTH/sub/**/../../name`` d'atteindre le parent du dossier autorisé.
        """
        normalized = pattern.replace("\\", "/")
        return any(part == ".." for part in normalized.split("/"))

    def find_files(self, pattern: str, max_results: int | None = None) -> dict[str, Any]:
        """Cherche des fichiers par pattern glob (ex: ``**/*.log``).
        Borne l'exploration et le nombre de résultats à ``max_results``
        (défaut ``MAX_FIND_FILES``) pour éviter de scanner/retourner des
        millions d'entrées sur une clef USB. Rejette tout pattern contenant
        un composant ``..`` (évasion de sandbox) et retourne les matches
        résolus (``Path.resolve``).
        """
        if max_results is None:
            max_results = MAX_FIND_FILES
        if self._contains_path_traversal(pattern):
            _logger.warning("Tentative de path traversal bloquée (pattern ..) : %s", pattern)
            return self._error_response(
                "Pattern non autorisé (séquence .. interdite)",
                "not_authorized",
            )
        try:
            resolved = self._resolve_real_path(os.path.dirname(pattern))
            self._check_authorized(resolved)
            matches: list[str] = []
            for match in glob_mod.iglob(pattern, recursive=True):
                matches.append(str(Path(match).resolve()))
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
