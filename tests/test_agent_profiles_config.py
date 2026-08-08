"""Tests — config.agent_profiles (modèle configuré par agent)."""
import json

from config import agent_profiles


def _write_profiles(tmp_path, content: dict):
    path = tmp_path / "agent_profiles.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


class TestModelForAgent:
    def test_returns_configured_model(self, tmp_path, monkeypatch):
        path = _write_profiles(tmp_path, {
            "profiles": {"techlead": {"model": "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"}}
        })
        monkeypatch.setattr(agent_profiles, "PROFILES_FILE", path)
        assert agent_profiles.model_for_agent("techlead") == (
            "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"
        )

    def test_unknown_agent_returns_none(self, tmp_path, monkeypatch):
        path = _write_profiles(tmp_path, {"profiles": {"techlead": {"model": "x"}}})
        monkeypatch.setattr(agent_profiles, "PROFILES_FILE", path)
        assert agent_profiles.model_for_agent("inconnu") is None

    def test_routing_key_maps_to_profile_model(self, tmp_path, monkeypatch):
        """Bug réel clé USB : @orchestrateur/@dev → agent_key "dev" n'existe
        pas dans agent_profiles.json (clés = profils) → fallback
        first_available() → moondream (modèle vision) → chat absurde.
        Les clés de routage doivent résoudre vers le profil associé
        (même mapping que agents/factory.py)."""
        path = _write_profiles(tmp_path, {
            "profiles": {
                "techlead": {"model": "TECHLEAD_MODEL"},
                "orchestrateur": {"model": "ORCHESTRATEUR_MODEL"},
            },
        })
        monkeypatch.setattr(agent_profiles, "PROFILES_FILE", path)
        assert agent_profiles.model_for_agent("dev") == "TECHLEAD_MODEL"
        assert agent_profiles.model_for_agent("hardware") == "ORCHESTRATEUR_MODEL"

    def test_missing_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(agent_profiles, "PROFILES_FILE", tmp_path / "absent.json")
        assert agent_profiles.model_for_agent("techlead") is None

    def test_corrupted_json_returns_none(self, tmp_path, monkeypatch):
        path = tmp_path / "agent_profiles.json"
        path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(agent_profiles, "PROFILES_FILE", path)
        assert agent_profiles.model_for_agent("techlead") is None
