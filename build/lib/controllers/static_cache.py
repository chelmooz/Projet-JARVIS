"""Cache des fichiers statiques — Cache-Control + ETag.

Helpers et StaticFiles spécialisé pour poser des headers de cache sur
les assets du dossier static/ (frontend). Les endpoints API ne sont
pas concernés : seuls les fichiers du STATIC_DIR reçoivent ces headers.
"""
import hashlib
import os

from fastapi import Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

# Durées de cache (secondes).
ASSET_MAX_AGE = 3600  # .js / .css / images : long, contenu versionné par nom
HTML_MAX_AGE = 60     # .html (SPA) : court, pour éviter un frontend périmé

# Extensions considérées comme des assets cacheables.
CACHEABLE_EXT = {
    ".js", ".css", ".html", ".htm", ".png", ".jpg", ".jpeg",
    ".svg", ".ico", ".json", ".woff", ".woff2", ".map",
}


def cache_control_for(full_path: str) -> str:
    """Retourne la directive Cache-Control selon l'extension du fichier."""
    ext = os.path.splitext(full_path)[1].lower()
    if ext == ".html" or ext == ".htm":
        return f"public, max-age={HTML_MAX_AGE}"
    return f"public, max-age={ASSET_MAX_AGE}"


def compute_etag(full_path: str) -> str:
    """Calcule un ETag stable basé sur mtime + taille (pas de lecture fichier)."""
    st = os.stat(full_path)
    raw = f"{st.st_mtime}:{st.st_size}:{os.path.basename(full_path)}".encode()
    return '"' + hashlib.sha256(raw).hexdigest() + '"'


def serve_cached_file(full_path: str, request: Request = None) -> Response:
    """Sert un fichier statique avec Cache-Control + ETag et gestion 304.

    Renvoie None si le fichier n'existe pas (à traiter par l'appelant).
    """
    if not os.path.isfile(full_path):
        return None
    etag = compute_etag(full_path)
    cc = cache_control_for(full_path)
    if_none_match = request.headers.get("if-none-match") if request else None
    if if_none_match and if_none_match == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cc})
    return FileResponse(
        full_path,
        headers={"Cache-Control": cc, "ETag": etag},
    )


class CachedStaticFiles(StaticFiles):
    """StaticFiles qui ajoute Cache-Control + ETag sur chaque réponse."""

    async def get_response(self, path: str, scope) -> Response:
        # Laisse StaticFiles gérer redirects / 404 / range.
        response = await super().get_response(path, scope)
        full_path = os.path.join(self.directory, path)
        if not os.path.isfile(full_path):
            return response
        etag = compute_etag(full_path)
        request = Request(scope)
        if_none_match = request.headers.get("if-none-match")
        if if_none_match and if_none_match == etag:
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": cache_control_for(full_path)},
            )
        response.headers["Cache-Control"] = cache_control_for(full_path)
        response.headers["ETag"] = etag
        return response
