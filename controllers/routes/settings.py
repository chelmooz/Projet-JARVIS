"""Routes Settings — API de préférences utilisateur (including offline mode)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from config.paths import PREFERENCES_FILE
from services.file_utils import write_json_atomic
from services.selector import read_preferences

router = APIRouter(tags=["settings"])


class SettingsUpdate(BaseModel):
    key: str
    value: bool | str | int | float | list | dict | None


@router.get("/api/settings")
def get_settings() -> dict:
    """Retourne les préférences utilisateur actuelles.

    Laisse sync : ``read_preferences()`` lit un fichier JSON sur le disque (I/O bloquant).
    """
    return read_preferences()


@router.put("/api/settings")
def update_settings(body: SettingsUpdate) -> dict:
    """Met à jour une clé de préférence (ex: offline)."""
    prefs = read_preferences()
    prefs[body.key] = body.value
    write_json_atomic(PREFERENCES_FILE, prefs, indent=4)
    return {"ok": True, "key": body.key, "value": body.value}


__all__ = ["router"]
