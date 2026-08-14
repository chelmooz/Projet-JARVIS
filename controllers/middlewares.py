"""Middlewares FastAPI : CORS, profilage, audit, sécurité, quota, limite de body.

Politique de sécurité :
- CSP ``default-src 'self'`` sans ``'unsafe-inline'`` ; les scripts/styles
  inline exigent un nonce par requête (``request.state.csp_nonce``). L'UI
  locale ne contient pas de JS inline (modules externes uniquement).
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from config.constants import CORS_ORIGIN, JARVIS_PORT, MAX_BODY_SIZE
from services import profiling
from services.ratelimit import MAX_REQUESTS, WINDOW, check_rate_limit

_logger = logging.getLogger(__name__)

MiddlewareHandler = Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]


async def _body_size_limiter(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
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
        return bytes(request.scope.get("_cached_body", b""))

    # Pattern Starlette : ``request.body()`` consomme le flux. On le met en cache
    # sur la scope et on remplace la méthode par une lecture du cache, sinon les
    # handlers en aval recevraient un flux épuisé (body vide).
    request.body = _read_body  # type: ignore[method-assign]
    return await call_next(request)


def setup_middlewares(app: FastAPI) -> None:
    """Enregistre CORS + middlewares (profilage, audit, sécurité, quota, body).

    Ordre d'exécution (requête entrante) — Starlette exécute les middlewares
    dans l'ordre INVERSE de leur enregistrement (le dernier enregistré est le
    plus externe, donc le premier exécuté) :

        1. ``_body_size_limiter``      rejette les body > MAX_BODY_SIZE avant tout
        2. ``_rate_limit_middleware``  limite le débit par IP
        3. ``_security_headers_middleware``  headers de sécurité sur la réponse
        4. ``_audit_log_middleware``   trace les POST
        5. ``_slow_endpoint_profiler`` profile les endpoints lents
        6. CORS (conditionnel sur JARVIS_ENABLE_OPENWEBUI=1)

    Cet ordre est volontaire : les garde-fous (body, quota) sont les plus
    externes pour rejeter au plus tôt, avant tout traitement métier.
    """
    local_port = f"http://localhost:{JARVIS_PORT}"

    # Add CORS middleware only if OpenWebUI is enabled
    if os.environ.get("JARVIS_ENABLE_OPENWEBUI", "0") == "1":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[local_port, f"http://127.0.0.1:{JARVIS_PORT}", CORS_ORIGIN],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def _slow_endpoint_profiler(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        debut = time.monotonic()
        resp = await call_next(request)
        duree = time.monotonic() - debut
        if duree >= profiling.SLOW_THRESHOLD:
            profiling.record_slow(request.url.path, duree)
            _logger.warning(
                "SLOW ENDPOINT %s — %.3fs (> %ss)",
                request.url.path,
                duree,
                profiling.SLOW_THRESHOLD,
            )
        return resp

    @app.middleware("http")
    async def _audit_log_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
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
    async def _security_headers_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            f"style-src 'self' 'nonce-{nonce}'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "form-action 'self'"
        )
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        return resp

    @app.middleware("http")
    async def _rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = check_rate_limit(client_ip)
        if not allowed:
            return JSONResponse(
                {"error": "Too many requests", "retry_after": WINDOW},
                status_code=429,
                headers={"Retry-After": str(WINDOW)},  # conformité HTTP 429 (header standard)
            )
        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS)
        resp.headers["X-RateLimit-Remaining"] = str(remaining)
        return resp

    app.middleware("http")(_body_size_limiter)


__all__ = ["setup_middlewares"]
