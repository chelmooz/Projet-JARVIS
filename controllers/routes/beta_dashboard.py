"""Route for beta dashboard — mounted only when JARVIS_BETA_DASHBOARD=1."""

from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from config.paths import STATIC_DIR

router = APIRouter()


@router.get("/beta-dashboard")
def get_beta_dashboard():
    """Renvoie le dashboard bêta si activé et présent.

    Note : la vérification de la variable d'environnement est une
    défense en profondeur (le routeur n'est monté que si == '1').
    """
    if os.environ.get("JARVIS_BETA_DASHBOARD") != "1":
        return JSONResponse({"error": "Not enabled"}, status_code=404)

    path = STATIC_DIR / "beta-dashboard.html"
    if not path.is_file():
        return JSONResponse({"error": "Not found"}, status_code=404)

    return FileResponse(path)


__all__ = ["router"]
