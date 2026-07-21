"""Middlewares FastAPI : CORS, profilage, audit, securite, quota, limite de body."""

import logging
import time

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.constants import CORS_ORIGIN, JARVIS_PORT, MAX_BODY_SIZE
from services.profiling import SLOW_THRESHOLD, record_slow
from services.ratelimit import MAX_REQUESTS, check_rate_limit

_logger = logging.getLogger("jarvis.context")


async def _body_size_limiter(request: Request, call_next):
    """S-2 : refuse les requetes dont le body depasse MAX_BODY_SIZE (413).

    Verifie d'abord l'en-tete Content-Length (cas nominal, sans consommer
    le flux), puis lit le flux pour detecter un depassement sur les requetes
    chunked/streamees. Le corps lu est mis en cache sur la scope pour les
    handlers en aval (sinon flux epuise).
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
            pass
    body = await request.body()
    if len(body) > limit:
        return JSONResponse(
            {"error": "Payload too large", "max_bytes": limit},
            status_code=413,
        )
    request.scope["_cached_body"] = body

    async def _read_body() -> bytes:
        return request.scope.get("_cached_body", b"")

    request.body = _read_body  # type: ignore[assignment]
    return await call_next(request)


def _setup_middlewares(app):
    """Enregistre le CORS et les middlewares de profilage, audit, securite, quota."""
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
        if duree >= SLOW_THRESHOLD:
            record_slow(request.url.path, duree)
            _logger.warning("SLOW ENDPOINT %s — %.3fs (> %ss)", request.url.path, duree, SLOW_THRESHOLD)
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
        resp.headers["X-XSS-Protection"] = "1; mode=block"
        return resp

    @app.middleware("http")
    async def _rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = check_rate_limit(client_ip)
        if not allowed:
            return JSONResponse(
                {"error": "Too many requests", "retry_after": 60}, status_code=429
            )
        resp = await call_next(request)
        resp.headers["X-RateLimit-Limit"] = str(MAX_REQUESTS)
        resp.headers["X-RateLimit-Remaining"] = str(remaining)
        return resp

    app.middleware("http")(_body_size_limiter)
