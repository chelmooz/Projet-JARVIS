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

    def test_missing_file_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(agent_profiles, "PROFILES_FILE", tmp_path / "absent.json")
        assert agent_profiles.model_for_agent("techlead") is None

    def test_corrupted_json_returns_none(self, tmp_path, monkeypatch):
        path = tmp_path / "agent_profiles.json"
        path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(agent_profiles, "PROFILES_FILE", path)
        assert agent_profiles.model_for_agent("techlead") is None
