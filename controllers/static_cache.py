"""Cache des fichiers statiques — Cache-Control + ETag + Compression gzip/br.

Helpers et StaticFiles spécialisé pour poser des headers de cache sur
les assets du dossier static/ (frontend). Les endpoints API ne sont
pas concernés : seuls les fichiers du STATIC_DIR reçoivent ces headers.

Pré-compression gzip/br des gros fichiers (ex: chart.umd.min.js ~206 Ko → ~75 Ko gzip).
"""

from __future__ import annotations

import gzip
import hashlib
import os
from typing import Any

from fastapi import Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

# Durées de cache (secondes).
ASSET_MAX_AGE = 3600  # .js / .css / images : long, contenu versionné par nom.
HTML_MAX_AGE = 60  # .html (SPA) : court, pour éviter un frontend périmé.

# Extensions considérées comme des assets cacheables (single source of truth).
# Tout fichier du STATIC_DIR dont l'extension est absente reçoit ``no-store``.
CACHEABLE_EXT = {
    ".js",
    ".css",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".avif",
    ".svg",
    ".ico",
    ".json",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".map",
}

# Fichiers à pré-compresser (chemins relatifs à STATIC_DIR).
# chart.umd.min.js ~206 Ko → ~75 Ko gzip / ~68 Ko brotli.
PRECOMPRESS_FILES = {
    "assets/js/chart.umd.min.js",
}

# Cache des fichiers pré-compressés : {relative_path: (gzip_bytes, brotli_bytes_ou_None)}
# br vaut None quand le paquet brotli est absent au runtime — jamais de gzip
# étiqueté comme br (Content-Encoding factice = corruption client).
_precompressed_cache: dict[str, tuple[bytes, bytes | None]] = {}
_precompressed_ready = False


def _precompress_files(static_dir: str) -> None:
    """Pré-compresse les gros fichiers statiques en gzip et brotli.

    Appelé une seule fois au démarrage (lazy init dans CachedStaticFiles).
    """
    global _precompressed_ready
    if _precompressed_ready:
        return

    for rel_path in PRECOMPRESS_FILES:
        full_path = os.path.join(static_dir, rel_path)
        if not os.path.isfile(full_path):
            continue
        with open(full_path, "rb") as f:
            content = f.read()
        # gzip
        gz = gzip.compress(content, compresslevel=9)
        # brotli (optionnel — fallback à None, jamais à gzip pour éviter un
        # Content-Encoding: br mensonger qui casserait le décodage client).
        br: bytes | None
        try:
            import brotli

            br = brotli.compress(content, quality=11)
        except ImportError:
            br = None
        _precompressed_cache[rel_path] = (gz, br)

    _precompressed_ready = True


def cache_control_for(full_path: str) -> str:
    """Retourne la directive Cache-Control selon l'extension du fichier.

    JS/CSS : ``no-cache`` (pas ``no-store``) — le fichier reste mis en cache
    par le navigateur, mais une requête conditionnelle (``If-None-Match``)
    est envoyée à *chaque* chargement. L'ETag (mtime+taille, cf.
    ``compute_etag``) change dès qu'un fichier est modifié : la nouvelle
    version est donc servie immédiatement après un simple F5, sans qu'un
    redémarrage serveur ou un hard-refresh (Ctrl+Shift+R) soit nécessaire.
    Avant ce correctif, ``max-age=3600`` faisait servir les anciens
    ``tools.js``/``style.css`` pendant 1h même après restart JARVIS, car les
    imports ES modules (``import ... from './modules/tools.js'``) n'ont pas
    de query string versionnée à invalider (cf. historique — bug page Outils).
    """
    ext = os.path.splitext(full_path)[1].lower()
    if ext not in CACHEABLE_EXT:
        return "no-store"
    if ext in (".html", ".htm"):
        return f"public, max-age={HTML_MAX_AGE}"
    if ext in (".js", ".css"):
        return "no-cache"
    return f"public, max-age={ASSET_MAX_AGE}"


def compute_etag(full_path: str) -> str:
    """Calcule un ETag stable basé sur mtime + taille (pas de lecture fichier)."""
    st = os.stat(full_path)
    raw = f"{st.st_mtime}:{st.st_size}:{os.path.basename(full_path)}".encode()
    return '"' + hashlib.sha256(raw).hexdigest() + '"'


def _cache_headers(full_path: str) -> dict[str, str]:
    """Construit les headers de cache (Cache-Control + ETag) pour un fichier."""
    return {"Cache-Control": cache_control_for(full_path), "ETag": compute_etag(full_path)}


def _get_precompressed(rel_path: str, accept_encoding: str) -> tuple[bytes, str] | None:
    """Retourne (contenu, content-encoding) si une version pré-compressée existe et est acceptée.

    Ne propose jamais ``br`` si le contenu brotli n'a pas réellement été produit
    (brotli importable = None dans le cache) : le client retombe alors sur gzip,
    déjà annoncé dans ``Accept-Encoding`` par tous les navigateurs modernes.
    """
    if rel_path not in _precompressed_cache:
        return None
    gz, br = _precompressed_cache[rel_path]
    # Préfère vraiment brotli si disponible (meilleure compression)
    if br is not None and "br" in accept_encoding:
        return br, "br"
    if "gzip" in accept_encoding:
        return gz, "gzip"
    return None


def serve_cached_file(full_path: str, request: Request | None = None) -> Response | None:
    """Sert un fichier statique avec Cache-Control + ETag + compression gzip/br.

    Renvoie ``None`` si le fichier n'existe pas (à traiter par l'appelant).
    """
    if not os.path.isfile(full_path):
        return None

    headers = _cache_headers(full_path)

    # Compression pré-calculée pour les gros fichiers
    if request is not None:
        static_dir = os.environ.get("JARVIS_STATIC_DIR", "")
        if static_dir:
            try:
                rel_path = os.path.relpath(full_path, static_dir).replace("\\", "/")
                precompressed = _get_precompressed(rel_path, request.headers.get("accept-encoding", ""))
                if precompressed:
                    content, encoding = precompressed
                    headers["Content-Encoding"] = encoding
                    headers["Content-Length"] = str(len(content))
                    if request.headers.get("if-none-match") == headers["ETag"]:
                        return Response(status_code=304, headers=headers)
                    return Response(content=content, media_type=_guess_media_type(full_path), headers=headers)
            except ValueError:
                pass  # full_path n'est pas dans static_dir

    if request is not None and request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    return FileResponse(full_path, headers=headers)


def _guess_media_type(full_path: str) -> str:
    """Devine le media type depuis l'extension."""
    ext = os.path.splitext(full_path)[1].lower()
    return {
        ".js": "application/javascript",
        ".css": "text/css",
        ".html": "text/html",
        ".htm": "text/html",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".map": "application/json",
    }.get(ext, "application/octet-stream")


class CachedStaticFiles(StaticFiles):
    """StaticFiles qui ajoute Cache-Control + ETag + compression gzip/br sur chaque réponse."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Initialisation lazy de la pré-compression
        if self.directory:
            _precompress_files(str(self.directory))

    async def get_response(self, path: str, scope: Scope) -> Response:
        # Laisse StaticFiles gérer redirects / 404 / range.
        response = await super().get_response(path, scope)
        full_path = os.path.join(self.directory or "", path)
        if not os.path.isfile(full_path):
            return response

        headers = _cache_headers(full_path)

        # Compression pré-calculée
        request = Request(scope)
        accept_encoding = request.headers.get("accept-encoding", "")
        if self.directory:
            try:
                rel_path = os.path.relpath(full_path, self.directory).replace("\\", "/")
                precompressed = _get_precompressed(rel_path, accept_encoding)
                if precompressed:
                    content, encoding = precompressed
                    headers["Content-Encoding"] = encoding
                    headers["Content-Length"] = str(len(content))
                    if request.headers.get("if-none-match") == headers["ETag"]:
                        return Response(status_code=304, headers=headers)
                    return Response(content=content, media_type=_guess_media_type(full_path), headers=headers)
            except ValueError:
                pass

        if request.headers.get("if-none-match") == headers["ETag"]:
            return Response(status_code=304, headers=headers)
        response.headers.update(headers)
        return response


__all__ = ["CachedStaticFiles", "serve_cached_file", "cache_control_for", "compute_etag"]
