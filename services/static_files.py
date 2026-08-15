"""Static file serving for JARVIS frontend assets."""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response

from controllers.static_cache import _cache_headers, cache_control_for


def serve_static_file(request: Request, path: str) -> Response:
    """Sert un fichier statique avec en-têtes de cache ETag + Cache-Control."""
    static_dir = os.environ.get("JARVIS_STATIC_DIR", "static")
    full_path = os.path.join(static_dir, path)

    if not os.path.isfile(full_path):
        return JSONResponse(content={"error": "not found"}, status_code=404)

    headers = _cache_headers(full_path)

    # Gestion du conditionnel If-None-Match / ETag : 304 sans corps (RFC 7232 §4.1)
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)

    # Ajout des en-têtes de cache
    headers["Cache-Control"] = cache_control_for(full_path)
    return FileResponse(full_path, headers=headers)
