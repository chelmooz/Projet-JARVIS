"""Lot 3.3 — Agents API (TDD, sans Ollama).

Teste ``GET /api/agents`` (liste profils) et ``POST /api/agents/assign``
(assignation + profil inconnu 404 + modèle invalide 400 + fichier profils absent 500).
Les chemins de fichiers sont redirigés vers ``tmp_path`` (aucune mutation du dépôt).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app

VALID_MODEL = "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    profiles = {
        "profiles": {"dev": {"model": "old"}, "cyber": {"model": "old"}},
        "agent_model_map": {"dev": "old", "cyber": "old"},
    }
    pf = tmp_path / "agent_profiles.json"
    pf.write_text(json.dumps(profiles), encoding="utf-8")
    prefs = tmp_path / "model_preferences.json"
    prefs.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("controllers.routes.agents.PROFILES_FILE", str(pf))
    monkeypatch.setattr("controllers.routes.agents.PREFERENCES_PATH", str(prefs))
    app = create_app()
    return TestClient(app)


def test_list_agents_200(client: TestClient) -> None:
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "profiles" in data
    assert isinstance(data["routing_prefixes"], list)


def test_assign_valid_profile_200(client: TestClient) -> None:
    resp = client.post("/api/agents/assign", json={"profile": "dev", "model": VALID_MODEL})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["profile"] == "dev"
    assert body["model"] == VALID_MODEL


def test_assign_unknown_profile_404(client: TestClient) -> None:
    resp = client.post("/api/agents/assign", json={"profile": "ghost", "model": VALID_MODEL})
    assert resp.status_code == 404


def test_assign_invalid_model_400(client: TestClient) -> None:
    # Modèle ne contenant que des caractères non autorisés -> safe_model_name("") -> 400.
    resp = client.post("/api/agents/assign", json={"profile": "dev", "model": "   "})
    assert resp.status_code == 400


def test_list_agents_missing_file_500(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "does_not_exist.json"
    monkeypatch.setattr("controllers.routes.agents.PROFILES_FILE", str(missing))
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/agents")
    assert resp.status_code == 500
