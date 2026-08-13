# controllers/routes/files.py
"""Route API -- Operations fichiers (Analyse Path).

Endpoints :
POST   /api/files/authorize   -- Autoriser un dossier
DELETE /api/files/authorize   -- Revoker un dossier
GET    /api/files/authorized  -- Lister les dossiers autorisés
POST   /api/files/list        -- Lister le contenu d'un dossier
POST   /api/files/read        -- Lire un fichier (max 10 Ko)
POST   /api/files/find        -- Chercher fichiers par pattern glob
GET    /api/files/browse      -- Naviguer dans un dossier deja autorisé (GET)
GET    /api/files/drives      -- Lister les lecteurs/racines disponibles
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

_logger = logging.getLogger(__name__)

from controllers.context import get_app_context  # noqa: E402
from controllers.di import AppContext  # noqa: E402
from models.schemas import (  # noqa: E402  # avoid circular import
    AuthorizePathRequest,
    FilePathRequest,
    FindFilesRequest,
)

router = APIRouter()


# ------------------------------------------------------------------
# Autorisation / Revocation
# ------------------------------------------------------------------
@router.post("/api/files/authorize")
def authorize_path(body: AuthorizePathRequest, context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    assert context.file_system is not None
    return {"success": context.file_system.authorize_path(body.path), "path": body.path}


@router.delete("/api/files/authorize")
def revoke_path(body: AuthorizePathRequest, context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    assert context.file_system is not None
    return {"success": context.file_system.revoke_path(body.path), "path": body.path}


# ------------------------------------------------------------------
# Liste des dossiers autorisés
# ------------------------------------------------------------------
@router.get("/api/files/authorized")
async def list_authorized(context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    assert context.file_system is not None
    # list_authorized() lit un ensemble en mémoire : safe en async.
    return {"paths": context.file_system.list_authorized()}


# ------------------------------------------------------------------
# Operations fichier (necessitent une autorisation prealable)
# ------------------------------------------------------------------
@router.post("/api/files/list")
def list_dir(body: FilePathRequest, context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    assert context.file_system is not None
    return context.file_system.list_dir(body.path)


@router.post("/api/files/read")
def read_file(body: FilePathRequest, context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    assert context.file_system is not None
    return context.file_system.read_file(body.path)


@router.post("/api/files/find")
def find_files(body: FindFilesRequest, context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    assert context.file_system is not None
    return context.file_system.find_files(body.pattern)


# ------------------------------------------------------------------
# Navigation (GET) -- complete l'UI d'analyse Path
# ------------------------------------------------------------------
@router.get("/api/files/browse")
def browse_dir(path: str = ".", context: AppContext = Depends(get_app_context)) -> dict[str, Any]:
    """Navigue dans un dossier deja autorisé (même contrat sécurisé que list_dir).
    Délègue a FileSystemService.list_dir : verifie la sandbox + l'autorisation
    prealable, refuse toute traversée hors périmètre.
    """
    assert context.file_system is not None
    return context.file_system.list_dir(path)


@router.get("/api/files/drives")
def list_drives() -> dict[str, Any]:
    """Liste les lecteurs/racines disponibles (cross-platform via psutil)."""
    try:
        import psutil

        drives = [str(p.mountpoint) for p in psutil.disk_partitions(all=False)]
    except Exception:
        _logger.warning("psutil.disk_partitions indisponible, liste de lecteurs vide")
        drives = []
    return {"success": True, "drives": drives}


__all__ = ["router"]
