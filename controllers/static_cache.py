"""Cache des fichiers statiques — Cache-Control + ETag.

Helpers et StaticFiles spécialisé pour poser des headers de cache sur
les assets du dossier static/ (frontend). Les endpoints API ne sont
pas concernés : seuls les fichiers du STATIC_DIR reçoivent ces headers.
"""

from __future__ import annotations

import hashlib
import os

from fastapi import Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

# Durées de cache (secondes).
ASSET_MAX_AGE = 3600  # .js / .css / images : long, contenu versionné par nom.
HTML_MAX_AGE = 60     # .html (SPA) : court, pour éviter un frontend périmé.

# Extensions considérées comme des assets cacheables (single source of truth).
# Tout fichier du STATIC_DIR dont l'extension est absente reçoit ``no-store``.
CACHEABLE_EXT = {
    ".js", ".css", ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp",
    ".gif", ".avif", ".svg", ".ico", ".json", ".woff", ".woff2",
    ".ttf", ".otf", ".map",
}


def cache_control_for(full_path: str) -> str:
    """Retourne la directive Cache-Control selon l'extension du fichier."""
    ext = os.path.splitext(full_path)[1].lower()
    if ext not in CACHEABLE_EXT:
        return "no-store"
    if ext in (".html", ".htm"):
        return f"public, max-age={HTML_MAX_AGE}"
    return f"public, max-age={ASSET_MAX_AGE}"


def compute_etag(full_path: str) -> str:
    """Calcule un ETag stable basé sur mtime + taille (pas de lecture fichier)."""
    st = os.stat(full_path)
    raw = f"{st.st_mtime}:{st.st_size}:{os.path.basename(full_path)}".encode()
    return '"' + hashlib.sha256(raw).hexdigest() + '"'


def _cache_headers(full_path: str) -> dict[str, str]:
    """Construit les headers de cache (Cache-Control + ETag) pour un fichier."""
    return {"Cache-Control": cache_control_for(full_path), "ETag": compute_etag(full_path)}


def serve_cached_file(full_path: str, request: Request | None = None) -> Response | None:
    """Sert un fichier statique avec Cache-Control + ETag et gestion 304.

    Renvoie ``None`` si le fichier n'existe pas (à traiter par l'appelant).
    """
    if not os.path.isfile(full_path):
        return None
    headers = _cache_headers(full_path)
    if request is not None and request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return FileResponse(full_path, headers=headers)


class CachedStaticFiles(StaticFiles):
    """StaticFiles qui ajoute Cache-Control + ETag sur chaque réponse."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        # Laisse StaticFiles gérer redirects / 404 / range.
        response = await super().get_response(path, scope)
        full_path = os.path.join(self.directory, path)
        if not os.path.isfile(full_path):
            return response
        headers = _cache_headers(full_path)
        if Request(scope).headers.get("if-none-match") == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        response.headers.update(headers)
        return response


__all__ = ["CachedStaticFiles", "serve_cached_file", "cache_control_for", "compute_etag"]
