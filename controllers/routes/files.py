"""Route API — Opérations fichiers (Analyse Path).

Endpoints :
  POST   /api/files/authorize   — Autoriser un dossier
  DELETE /api/files/authorize   — Révoquer un dossier
  GET    /api/files/authorized  — Lister les dossiers autorisés
  POST   /api/files/list        — Lister le contenu d'un dossier
  POST   /api/files/read        — Lire un fichier (max 10 Ko)
  POST   /api/files/find        — Chercher fichiers par pattern glob
  GET    /api/files/browse      — Naviguer dans un dossier déjà autorisé (GET)
  GET    /api/files/drives      — Lister les lecteurs/racines disponibles
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from controllers.responses import ok
from models.schemas import AuthorizePathRequest, FilePathRequest, FindFilesRequest
from services.file_system import FileSystemService

_logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton instance (stateful: holds authorized paths)
_FILE_SYSTEM_SERVICE = FileSystemService()


def get_file_system_service() -> FileSystemService:
    """Dependency: returns the singleton FileSystemService."""
    return _FILE_SYSTEM_SERVICE


# ------------------------------------------------------------------
# Autorisation / Révocation
# ------------------------------------------------------------------

@router.post("/api/files/authorize")
def authorize_path(
    body: AuthorizePathRequest,
    fs: Annotated[FileSystemService, Depends(get_file_system_service)],
):
    success = fs.authorize_path(body.path)
    _logger.info("Path authorized: %s (success=%s)", body.path, success)
    return ok({"success": success, "path": body.path})


@router.delete("/api/files/authorize")
def revoke_path(
    body: AuthorizePathRequest,
    fs: Annotated[FileSystemService, Depends(get_file_system_service)],
):
    success = fs.revoke_path(body.path)
    _logger.info("Path revoked: %s (success=%s)", body.path, success)
    return ok({"success": success, "path": body.path})


# ------------------------------------------------------------------
# Liste des dossiers autorisés
# ------------------------------------------------------------------

@router.get("/api/files/authorized")
async def list_authorized(
    fs: Annotated[FileSystemService, Depends(get_file_system_service)],
):
    return ok({"paths": fs.list_authorized()})


# ------------------------------------------------------------------
# Opérations fichier (nécessitent une autorisation préalable)
# ------------------------------------------------------------------

@router.post("/api/files/list")
def list_dir(
    body: FilePathRequest,
    fs: Annotated[FileSystemService, Depends(get_file_system_service)],
):
    return ok(fs.list_dir(body.path))


@router.post("/api/files/read")
def read_file(
    body: FilePathRequest,
    fs: Annotated[FileSystemService, Depends(get_file_system_service)],
):
    return ok(fs.read_file(body.path))


@router.post("/api/files/find")
def find_files(
    body: FindFilesRequest,
    fs: Annotated[FileSystemService, Depends(get_file_system_service)],
):
    return ok(fs.find_files(body.pattern))


# ------------------------------------------------------------------
# Navigation (GET) — complète l'UI d'analyse Path
# ------------------------------------------------------------------

@router.get("/api/files/browse")
def browse_dir(
    path: str = ".",
    fs: Annotated[FileSystemService, Depends(get_file_system_service)] = Depends(get_file_system_service),
):
    """Navigue dans un dossier déjà autorisé (même contrat sécurisé que list_dir).

    Délègue à FileSystemService.list_dir : vérifie la sandbox + l'autorisation
    préalable, refuse toute traversée hors périmètre.
    """
    return ok(fs.list_dir(path))


@router.get("/api/files/drives")
def list_drives():
    """Liste les lecteurs/racines disponibles (cross-platform via psutil)."""
    try:
        import psutil
        drives = [p.mountpoint for p in psutil.disk_partitions(all=False)]
    except ImportError:
        _logger.warning("psutil not installed, cannot list drives")
        drives = []
    except Exception as e:
        _logger.warning("Failed to list drives: %s", e)
        drives = []
    return ok({"drives": drives})


__all__ = ["router"]
