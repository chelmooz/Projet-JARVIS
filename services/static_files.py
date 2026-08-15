"""Static file serving for JARVIS frontend assets."""

from __future__ import annotations

import os
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse

from controllers.static_cache import cache_control_for, compute_etag, _cache_headers, _guess_media_type


def serve_static_file(request: Request, path: str) -> JSONResponse:
    """Sert un fichier statique avec en-têtes de cache ETag + Cache-Control."""
    static_dir = os.environ.get("JARVIS_STATIC_DIR", "static")
    full_path = os.path.join(static_dir, path)

    if not os.path.isfile(full_path):
        return JSONResponse(content={"error": "not found"}, status_code=404)

    headers = _cache_headers(full_path)

    # Gestion du conditionnel If-None-Match / ETag
    if request.headers.get("if-none-match") == headers["ETag"]:
        return JSONResponse(status_code=304, headers=headers)

    # Ajout des en-têtes de cache
    headers["Cache-Control"] = cache_control_for(full_path)
    return JSONResponse(content=FileResponse(full_path), headers=headers)  # type: ignore