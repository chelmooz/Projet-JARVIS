"""Routes API — Accès étendu aux disques et partitions non-montées."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from services.extended_file_system import ExtendedFileSystemService

_logger = logging.getLogger(__name__)

router = APIRouter()


class MountExt4Request(BaseModel):
    disk_number: int = Field(..., ge=0, description="Numéro du disque physique")
    partition_number: int = Field(..., ge=1, description="Numéro de la partition")
    mount_letter: str | None = Field(
        None,
        pattern=r"^[A-Z]$",
        description="Lettre E-Z (auto si None)",
    )


class UnmountExt4Request(BaseModel):
    disk_number: int = Field(..., ge=0)
    partition_number: int = Field(..., ge=1)


class ReadExt4Request(BaseModel):
    disk_number: int = Field(..., ge=0)
    partition_number: int = Field(..., ge=1)
    target_path: str = Field("/", description="Chemin dans la partition")


_extended_fs_service = None


def get_extended_fs_service() -> ExtendedFileSystemService:
    """Singleton du service (lazy init au premier appel)."""
    global _extended_fs_service
    if _extended_fs_service is None:
        from services.extended_file_system import ExtendedFileSystemService

        _extended_fs_service = ExtendedFileSystemService()
    return _extended_fs_service


@router.get("/api/files/all_drives")
async def list_all_drives() -> dict[str, Any]:
    """Liste TOUS les disques physiques et leurs partitions."""
    try:
        return get_extended_fs_service().get_all_drives_extended()
    except Exception as e:
        _logger.error("Erreur all_drives : %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/files/mount_ext4")
async def mount_ext4(req: MountExt4Request) -> dict[str, Any]:
    """Monte une partition Linux via diskpart + service Ext2Fsd."""
    try:
        return get_extended_fs_service().mount_ext4_partition(
            req.disk_number,
            req.partition_number,
            req.mount_letter,
        )
    except Exception as e:
        _logger.error("Erreur mount_ext4 : %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/files/unmount_ext4")
async def unmount_ext4(req: UnmountExt4Request) -> dict[str, Any]:
    """Retire la lettre d'une partition précédemment montée."""
    try:
        ok = get_extended_fs_service().unmount_ext4_partition(
            req.disk_number,
            req.partition_number,
        )
        return {"success": ok}
    except Exception as e:
        _logger.error("Erreur unmount_ext4 : %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/files/read_ext4_direct")
async def read_ext4_direct(req: ReadExt4Request) -> dict[str, Any]:
    """Lecture directe ext4 via librairie Python (admin requis)."""
    try:
        return get_extended_fs_service().read_ext4_direct(
            req.disk_number,
            req.partition_number,
            req.target_path,
        )
    except Exception as e:
        _logger.error("Erreur read_ext4_direct : %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


__all__ = ["router"]
