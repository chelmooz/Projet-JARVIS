"""Tests MT-KB-L3h — Modèles de spécialité figés par défaut (source unique).

Politique (décision utilisateur) :
- ``config/agent_profiles.json`` est la SOURCE DE VÉRITÉ des modèles par
  profil, alignée sur les spécialités (dev->granite, cyber->deephat,
  network->foundation-sec, hardware->qwen).
- ``model_preferences.json`` ne porte plus de clés modèles (préférences
  utilisateur uniquement : offline, timeout...).
- ``select_model`` : modèle configuré d'abord, fallback UNIQUEMENT si le
  modèle est absent d'Ollama, jamais d'écriture automatique.
- Seule la route POST /api/agents/assign écrit agent_profiles.json
  (override utilisateur via l'onglet Agents).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.agent_profiles import model_for_agent
from controllers.router import create_app
from services.selector import fallback_models, select_model

SPECIALTY_GRANITE = "hf.co/bartowski/ibm-granite_granite-4.1-8b-GGUF:Q4_K_M"
SPECIALTY_DEEP_HAT = "hf.co/GGUF-A-Lot/DeepHat-V1-7B-GGUF:Q4_K_M"
SPECIALTY_FOUNDATION = "hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF:Q8_0"
SPECIALTY_QWEN = "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"


class _InstalledInference:
    """Double inférence : tous les modèles sont considérés installés (resolve = identité)."""

    def resolve_model(self, model: str) -> str | None:
        return model

    def first_available(self) -> str | None:
        return "generic-fallback"


def _fresh_prefs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simule l'état cible : model_preferences.json dépouillé (plus de model_map)."""
    monkeypatch.setattr("services.selector.read_preferences", lambda: {})


class TestSpecialtyDefaults:
    def test_dev_default_is_granite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``select_model("dev")`` sans override -> granite (spécialité code)."""
        _fresh_prefs(monkeypatch)
        assert select_model("dev", _InstalledInference()) == SPECIALTY_GRANITE

    def test_specialty_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """cyber->deephat, network->foundation-sec, hardware->qwen."""
        _fresh_prefs(monkeypatch)
        inference = _InstalledInference()
        assert select_model("cyber", inference) == SPECIALTY_DEEP_HAT
        assert select_model("network", inference) == SPECIALTY_FOUNDATION
        assert select_model("hardware", inference) == SPECIALTY_QWEN

    def test_config_source_matches_specialties(self) -> None:
        """agent_profiles.json (source de vérité) est aligné sur les spécialités."""
        assert model_for_agent("dev") == SPECIALTY_GRANITE
        assert model_for_agent("cyber") == SPECIALTY_DEEP_HAT
        assert model_for_agent("network") == SPECIALTY_FOUNDATION
        assert model_for_agent("hardware") == SPECIALTY_QWEN


class TestApiAgentsSpecialtyModels:
    def test_api_agents_returns_specialty_models(self) -> None:
        """GET /api/agents (état frais) renvoie les 4 modèles de spécialité.

        C'est exactement ce que le frontend affiche dans le dropdown Agents
        et le badge du chat.
        """
        app = create_app()
        resp = TestClient(app).get("/api/agents")
        assert resp.status_code == 200
        profiles = resp.json()["data"]["profiles"]
        assert profiles["techlead"]["model"] == SPECIALTY_GRANITE
        assert profiles["devops"]["model"] == SPECIALTY_FOUNDATION
        assert profiles["datasecu"]["model"] == SPECIALTY_DEEP_HAT
        assert profiles["orchestrateur"]["model"] == SPECIALTY_QWEN


class TestUserOverride:
    def test_user_override_respected_system_never_overwrites(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Après assign(techlead->qwen) : select_model("dev") -> qwen.

        ``select_model`` ne doit JAMAIS écrire agent_profiles.json : le
        contenu du fichier est identique avant et après l'appel.
        """
        profiles = {
            "profiles": {
                "techlead": {"model": SPECIALTY_GRANITE},
                "devops": {"model": SPECIALTY_FOUNDATION},
                "datasecu": {"model": SPECIALTY_DEEP_HAT},
                "orchestrateur": {"model": SPECIALTY_QWEN},
            },
            "agent_model_map": {
                "techlead": SPECIALTY_GRANITE,
                "devops": SPECIALTY_FOUNDATION,
                "datasecu": SPECIALTY_DEEP_HAT,
                "orchestrateur": SPECIALTY_QWEN,
            },
        }
        pf = tmp_path / "agent_profiles.json"
        pf.write_text(json.dumps(profiles), encoding="utf-8")
        monkeypatch.setattr("controllers.routes.agents.PROFILES_FILE", str(pf))
        monkeypatch.setattr("config.agent_profiles.PROFILES_FILE", str(pf))
        _fresh_prefs(monkeypatch)

        # Override utilisateur via la route (seul writer autorisé).
        app = create_app()
        resp = TestClient(app).post("/api/agents/assign", json={"profile": "techlead", "model": "qwen2.5:7b"})
        assert resp.status_code == 200

        assert select_model("dev", _InstalledInference()) == "qwen2.5:7b"
        assert fallback_models()["dev"] == SPECIALTY_GRANITE  # spécialité par défaut intacte

        # Verrou : select_model n'écrit jamais agent_profiles.json.
        after = json.loads(pf.read_text(encoding="utf-8"))
        assert after["profiles"]["techlead"]["model"] == "qwen2.5:7b"
        assert after["agent_model_map"]["techlead"] == "qwen2.5:7b"
        assert len(after["profiles"]) == 4  # aucune écriture parasite


def test_selector_never_writes_model_preferences(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``select_model`` ne touche jamais à model_preferences.json (dépouillé)."""
    prefs_path = tmp_path / "model_preferences.json"
    monkeypatch.setattr("services.selector.PREFERENCES_PATH", str(prefs_path))
    monkeypatch.setattr("services.selector.read_preferences", lambda: {})
    assert not prefs_path.exists()
    select_model("dev", _InstalledInference())
    assert not prefs_path.exists()
