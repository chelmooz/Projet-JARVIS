# controllers/routes/files.py
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

import psutil
from fastapi import APIRouter

from models.schemas import AuthorizePathRequest, FilePathRequest, FindFilesRequest
from services.file_system import FileSystemService

router = APIRouter()
_fs = FileSystemService()


# ------------------------------------------------------------------
# Autorisation / Révocation
# ------------------------------------------------------------------
@router.post("/api/files/authorize")
def authorize_path(body: AuthorizePathRequest):
    return {"success": _fs.authorize_path(body.path), "path": body.path}


@router.delete("/api/files/authorize")
def revoke_path(body: AuthorizePathRequest):
    return {"success": _fs.revoke_path(body.path), "path": body.path}


# ------------------------------------------------------------------
# Liste des dossiers autorisés
# ------------------------------------------------------------------
@router.get("/api/files/authorized")
async def list_authorized():
    # list_authorized() lit un ensemble en mémoire : safe en async.
    return {"paths": _fs.list_authorized()}


# ------------------------------------------------------------------
# Opérations fichier (nécessitent une autorisation préalable)
# ------------------------------------------------------------------
@router.post("/api/files/list")
def list_dir(body: FilePathRequest):
    return _fs.list_dir(body.path)


@router.post("/api/files/read")
def read_file(body: FilePathRequest):
    return _fs.read_file(body.path)


@router.post("/api/files/find")
def find_files(body: FindFilesRequest):
    return _fs.find_files(body.pattern)


# ------------------------------------------------------------------
# Navigation (GET) — complète l'UI d'analyse Path
# ------------------------------------------------------------------
@router.get("/api/files/browse")
def browse_dir(path: str = "."):
    """Navigue dans un dossier déjà autorisé (même contrat sécurisé que list_dir).
    Délègue à FileSystemService.list_dir : vérifie la sandbox + l'autorisation
    préalable, refuse toute traversée hors périmètre.
    """
    return _fs.list_dir(path)


@router.get("/api/files/drives")
def list_drives():
    """Liste les lecteurs/racines disponibles (cross-platform via psutil)."""
    try:
        drives = [p.mountpoint for p in psutil.disk_partitions(all=False)]
    except Exception:  # psutil indisponible / OS exotique -> liste vide
        drives = []
    return {"success": True, "drives": drives}


__all__ = ["router"]
