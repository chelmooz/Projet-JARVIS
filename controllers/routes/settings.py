"""Routes Settings — API de préférences utilisateur (including offline mode)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from config.paths import PREFERENCES_FILE
from services.file_utils import write_json_atomic
from services.selector import _prefs_cache, read_preferences

router = APIRouter(tags=["settings"])


class SettingsUpdate(BaseModel):
    key: str
    value: bool | str | int | float | list[Any] | dict[str, Any] | None


@router.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    """Retourne les préférences utilisateur actuelles.

    Déporté hors event loop via ``asyncio.to_thread`` (consistance avec
    ``/api/jarvis``, ROADMAP 17.5).
    """
    return await asyncio.to_thread(read_preferences)


@router.put("/api/settings")
async def update_settings(body: SettingsUpdate) -> dict[str, Any]:
    """Met à jour une clé de préférence (ex: offline)."""
    prefs = await asyncio.to_thread(read_preferences)
    prefs[body.key] = body.value
    await asyncio.to_thread(write_json_atomic, PREFERENCES_FILE, prefs, indent=4)
    # Invalide le cache pour que les lectures suivantes voient la nouvelle valeur
    _prefs_cache._mtime = 0.0
    _prefs_cache._cache.clear()
    return {"ok": True, "key": body.key, "value": body.value}


__all__ = ["router"]
