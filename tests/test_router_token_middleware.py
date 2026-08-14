"""Lot 8.A — Tests du middleware de vérification de token.

Couverture des 4 branches du middleware :
- header absent → 401
- fichier token absent → 503
- token invalide → 401
- token valide → passe
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ASGITransport

import pytest

from controllers.router import _register_middlewares

# Force token verification en définissant OpenWebUI activé
os.environ["JARVIS_ENABLE_OPENWEBUI"] = "1"


def _make_app() -> FastAPI:
    """Crée une app FastAPI avec le middleware de token inscrit."""
    app = FastAPI()
    _register_middlewares(app)
    # Routes de base pour que le middleware traite les requêtes
    app.get("/api/jarvis")(lambda: {"status": "ok"})
    app.get("/api/token-test")(lambda: {"status": "ok"})
    return app


@pytest.mark.asyncio
async def test_token_header_absent_returns_401() -> None:
    """Header X-JARVIS-Token manquant → 401."""
    app = _make_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/jarvis")
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Missing X-JARVIS-Token header"


@pytest.mark.asyncio
async def test_token_file_absent_returns_503() -> None:
    """Fichier .jarvis_token absent → 503."""
    app = _make_app()

    # S'assurer que le fichier n'existe pas
    token_file = Path(__file__).resolve().parent.parent / "memory" / ".jarvis_token"
    if token_file.exists():
        token_file.unlink()
    parent = token_file.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/jarvis", headers={"X-JARVIS-Token": "any_token"})
    assert response.status_code == 503
    data = response.json()
    assert data["detail"] == "Authentication token not available"


@pytest.mark.asyncio
async def test_token_invalid_returns_401() -> None:
    """Token invalide → 401."""
    app = _make_app()

    # Créer un fichier de token avec une mauvaise valeur
    token_file = Path(__file__).resolve().parent.parent / "memory" / ".jarvis_token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("wrong_token_value")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/jarvis", headers={"X-JARVIS-Token": "different_token"})
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Invalid X-JARVIS-Token"


@pytest.mark.asyncio
async def test_token_valid_passes() -> None:
    """Token valide → la requête passe vers l'application."""
    app = _make_app()

    # Créer un fichier de token avec la bonne valeur
    token_file = Path(__file__).resolve().parent.parent / "memory" / ".jarvis_token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text("valid_token_12345")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/jarvis", headers={"X-JARVIS-Token": "valid_token_12345"})
    # Doit passer (200) ou avoir un autre code selon l'état de l'application,
    # mais ne doit certainement pas être 401/503 lié au token
    assert response.status_code != 401
    assert response.status_code != 503