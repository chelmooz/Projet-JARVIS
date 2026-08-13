"""Lot 3.4 — Fichiers API (TDD, sans Ollama).

Valide le contrat fail-closed du ``FileSystemService`` via l'API :
- 200 + success pour un dossier autorisé DANS le sandbox ;
- refus (success False, error_type "not_authorized") pour un dossier non autorisé
  (même dans le sandbox) ou hors sandbox ;
- lecture d'un fichier inexistant -> success False ("Pas un fichier").

Le sandbox est fourni par la fixture ``sandbox_root`` (conftest) ; la config
d'autorisation est isolée dans un fichier tmp (aucune mutation du dépôt).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app
from services.file_system import FileSystemService


@pytest.fixture
def client(sandbox_root: Path) -> TestClient:
    # sandbox_root (conftest) définit JARVIS_FILES_SANDBOX_ROOT -> tmp_path.
    # Config d'autorisation isolée pour ne pas toucher le dépôt.
    auth_file = sandbox_root / "auth.json"
    fs = FileSystemService(config_path=auth_file)
    app = create_app()
    app.state.context = SimpleNamespace(file_system=fs)
    return TestClient(app)


def test_list_in_sandbox_200(client: TestClient, sandbox_root: Path) -> None:
    docs = sandbox_root / "docs"
    docs.mkdir()
    assert client.post("/api/files/authorize", json={"path": str(docs)}).json()["success"] is True
    resp = client.post("/api/files/list", json={"path": str(docs)})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_refuse_unauthorized_in_sandbox(client: TestClient, sandbox_root: Path) -> None:
    secret = sandbox_root / "secret"
    secret.mkdir()
    resp = client.post("/api/files/list", json={"path": str(secret)})
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "not_authorized"


def test_refuse_outside_sandbox(client: TestClient) -> None:
    outside = tempfile.mkdtemp()
    assert client.post("/api/files/authorize", json={"path": outside}).json()["success"] is False
    resp = client.post("/api/files/list", json={"path": outside})
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "not_authorized"


def test_read_nonexistent_file(client: TestClient, sandbox_root: Path) -> None:
    docs = sandbox_root / "docs"
    docs.mkdir()
    assert client.post("/api/files/authorize", json={"path": str(docs)}).json()["success"] is True
    resp = client.post("/api/files/read", json={"path": str(docs / "nope.txt")})
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == "Pas un fichier"
