"""Tests de securite MT-P4 : path traversal statique (S-1) et limite de body (S-2)."""
import os
from unittest.mock import MagicMock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import config.constants as constants
import controllers.context as context_mod
import controllers.middlewares as middlewares_mod
import controllers.router as router_mod


def test_path_traversal_returns_404():
    """S-1 : un chemin '../../etc/passwd' ne doit pas sortir de STATIC_DIR."""
    fake_req = MagicMock(spec=Request)
    resp = router_mod.serve_static("../../../../etc/passwd", fake_req)
    assert resp.status_code == 404


def test_path_traversal_nested_returns_404():
    resp = router_mod.serve_static("..%2f..%2f..%2fwindows/win.ini", MagicMock(spec=Request))
    assert resp.status_code == 404


def test_static_file_within_dir_is_served(monkeypatch):
    """Un fichier reel dans STATIC_DIR est servi (200), pas de regression."""
    tmp = os.path.join(constants.ROOT, ".pytest-temp", "mt_p4_static")
    os.makedirs(tmp, exist_ok=True)
    monkeypatch.setattr(router_mod, "STATIC_DIR", tmp)
    monkeypatch.setattr(context_mod, "STATIC_DIR", tmp)
    asset = os.path.join(tmp, "robots.txt")
    with open(asset, "w", encoding="utf-8") as f:
        f.write("ok")

    served = {"called": False}

    def fake_serve(full_path, request):
        served["called"] = True
        from fastapi.responses import Response

        return Response("ok")

    monkeypatch.setattr(router_mod, "serve_cached_file", fake_serve)
    # Appel direct du handler catch-all (hors pile FastAPI : le mont /static
    # n'interfere pas avec cette verification unitaire de la logique S-1).
    resp = router_mod.serve_static("robots.txt", MagicMock(spec=Request))
    assert resp.status_code == 200
    assert served["called"], "le fichier reel aurait du etre servi (pas de regression)"


def test_oversized_body_rejected(monkeypatch):
    """S-2 : un body depassant MAX_BODY_SIZE doit etre refuse (413)."""
    monkeypatch.setattr(constants, "MAX_BODY_SIZE", 50)
    monkeypatch.setattr(context_mod, "MAX_BODY_SIZE", 50)
    monkeypatch.setattr(middlewares_mod, "MAX_BODY_SIZE", 50)
    from controllers.context import _body_size_limiter

    app = FastAPI()
    app.middleware("http")(_body_size_limiter)

    @app.post("/echo")
    async def echo(request: Request):
        data = await request.body()
        return JSONResponse({"len": len(data)})

    tc = TestClient(app)
    big = "x" * 200
    resp = tc.post("/echo", content=big)
    assert resp.status_code == 413
    small = tc.post("/echo", content="x" * 10)
    assert small.status_code == 200
