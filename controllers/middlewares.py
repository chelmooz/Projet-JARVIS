"""Middlewares FastAPI : CORS, profilage, audit, sécurité, quota, limite de body.

Dettes signalées (non corrigées ici) :
- CSP : ``'unsafe-inline'`` sur script-src/style-src affaiblit la politique
  (nécessaire au JS inline de l'UI locale). Cible : nonce ou hash CSP.
- ``X-XSS-Protection`` est déprécié (ignoré des navigateurs modernes, peut
  introduire des bugs d'XSS auditor). Cible : omettre ou forcer à ``0``.
- ``retry_after: 60`` est hardcodé ; devrait être dérivé de la fenêtre réelle
  de ``services.ratelimit`` (single source of truth).
- ``_setup_middlewares`` est préfixé ``_`` mais importé par ``controllers/context.py``
  (symbole privé exporté). Cible : renommer en ``setup_middlewares`` (public)
  et mettre à jour l'import dans context.py (fichier déjà commité → coordination).
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.constants import CORS_ORIGIN, JARVIS_PORT, MAX_BODY_SIZE
from services import profiling
from services.ratelimit import MAX_REQUESTS, check_rate_limit

_logger = logging.getLogger(__name__)


async def _body_size_limiter(request: Request, call_next):
    """S-2 : refuse les requêtes dont le body dépasse MAX_BODY_SIZE (413).

    Vérifie d'abord l'en-tête Content-Length (cas nominal, sans consommer
    le flux), puis lit le flux pour détecter un dépassement sur les requêtes
    chunked/streamées. Le corps lu est mis en cache sur la scope pour les
    handlers en aval (sinon flux épuisé).
    """
    if request.method in ("GET", "HEAD", "OPTIONS", "DELETE"):
        return await call_next(request)
    limit = MAX_BODY_SIZE
    length_header = request.headers.get("content-length")
    if length_header is not None:
        try:
            if int(length_header) > limit:
                return JSONResponse(
                    {"error": "Payload too large", "max_bytes": limit},
                    status_code=413,
                )
        except ValueError:
            # Fin du fail-silent : un Content-Length malformé est observable
            # (debug), mais on ne bloque pas — fallback sur la lecture du flux.
            _logger.debug(
                "Content-Length non entier ignoré (%r) — fallback lecture du flux.",
                length_header,
            )
    body = await request.body()
    if len(body) > limit:
        return JSONResponse(
            {"error": "Payload too large", "max_bytes": limit},
            status_code=413,
        )
    request.scope["_cached_body"] = body

    async def _read_body() -> bytes:
        return request.scope.get("_cached_body", b"")

    # Pattern Starlette : ``request.body()`` consomme le flux. On le met en cache
    # sur la scope et on remplace la méthode par une lecture du cache, sinon les
    # handlers en aval recevraient un flux épuisé (body vide).
    request.body = _read_body  # type: ignore[assignment]
    return await call_next(request)


def _setup_middlewares(app: FastAPI) -> None:
    """Enregistre CORS + middlewares (profilage, audit, sécurité, quota, body).

    Ordre d'exécution (requête entrante) — Starlette exécute les middlewares
    dans l'ordre INVERSE de leur enregistrement (le dernier enregistré est le
    plus externe, donc le premier exécuté) :

        1. ``_body_size_limiter``      rejette les body > MAX_BODY_SIZE avant tout
        2. ``_rate_limit_middleware``  limite le débit par IP
        3. ``_security_headers_middleware``  headers de sécurité sur la réponse
        4. ``_audit_log_middleware``   trace les POST
        5. ``_slow_endpoint_profiler`` profile les endpoints lents
        6. CORS

    Cet ordre est volontaire : les garde-fous (body, quota) sont les plus
    externes pour rejeter au plus tôt, avant tout traitement métier.
    """
    local_port = f"http://localhost:{JARVIS_PORT}"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[local_port, f"http://127.0.0.1:{JARVIS_PORT}", CORS_ORIGIN],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _slow_endpoint_profiler(request: Request, call_next):
        debut = time.monotonic()
        resp = await call_next(request)
        duree = time.monotonic() - debut
        if duree >= profiling.SLOW_THRESHOLD:
            profiling.record_slow(request.url.path, duree)
            _logger.warning(
                "SLOW ENDPOINT %s — %.3fs (> %ss)", request.url.path, duree, profiling.SLOW_THRESHOLD,
            )
        return resp

    @app.middleware("http")
    async def _audit_log_middleware(request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        try:
            resp = await call_next(request)
        except Exception:
            _logger.warning("AUDIT POST %s from %s — EXCEPTION", request.url.path, client)
            raise
        if request.method == "POST":
            _logger.info("AUDIT POST %s from %s — %s", request.url.path, client, resp.status_code)
        return resp

    @app.middleware("http")
    async def _security_headers_middleware(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "form-action 'self'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        return resp

    @app.middleware("http")
    async def _rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = check_rate_limit(client_ip)
        if not allowed:
            return JSONResponse(
                {"error": "Too many requests", "retry_after": 60},
                status_code=429,
                headers={"Retry-After": "60"},  # conformité HTTP 429 (header standard)
            )
        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS)
        resp.headers["X-RateLimit-Remaining"] = str(remaining)
        return resp

    app.middleware("http")(_body_size_limiter)


__all__ = ["_setup_middlewares"]
