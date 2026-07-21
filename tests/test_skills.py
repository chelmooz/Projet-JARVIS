"""Tests pour services.skills — chargement et filtrage des skills activés."""
import json
import os
import sys

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.skills import get_enabled_skills_text, load_skills


class TestLoadSkills:
    """load_skills(): retourne un dict ou le défaut selon l'état du fichier."""

    def test_valid_file_returns_dict_with_skills(self, monkeypatch, tmp_path):
        cfg = tmp_path / "skills.json"
        data = {"version": "1.0", "skills": [{"id": "s1", "enabled": True, "prompt": "hello"}]}
        cfg.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr("services.skills.SKILLS_CONFIG", str(cfg))
        assert load_skills() == data

    def test_missing_file_returns_default_dict(self, monkeypatch, tmp_path):
        missing = tmp_path / "nonexistent.json"
        monkeypatch.setattr("services.skills.SKILLS_CONFIG", str(missing))
        assert load_skills() == {"version": "1.0", "skills": []}

    def test_malformed_json_returns_default_dict(self, monkeypatch, tmp_path):
        cfg = tmp_path / "skills.json"
        cfg.write_text("{broken", encoding="utf-8")
        monkeypatch.setattr("services.skills.SKILLS_CONFIG", str(cfg))
        assert load_skills() == {"version": "1.0", "skills": []}


class TestGetEnabledSkillsText:
    """get_enabled_skills_text(): formate les skills activés pour injection LLM."""

    def test_enabled_skills_returns_formatted_text(self, monkeypatch, tmp_path):
        cfg = tmp_path / "skills.json"
        data = {
            "version": "1.0",
            "skills": [
                {"id": "s1", "enabled": True, "prompt": "Skill A"},
                {"id": "s2", "enabled": False, "prompt": "Skill B"},
                {"id": "s3", "enabled": True, "prompt": "Skill C"},
            ],
        }
        cfg.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr("services.skills.SKILLS_CONFIG", str(cfg))
        assert get_enabled_skills_text() == "[Skills actifs]\nSkill A\n\nSkill C"

    def test_no_enabled_skills_returns_empty_string(self, monkeypatch, tmp_path):
        cfg = tmp_path / "skills.json"
        data = {
            "version": "1.0",
            "skills": [
                {"id": "s1", "enabled": False, "prompt": "Skill A"},
                {"id": "s2", "enabled": False, "prompt": "Skill B"},
            ],
        }
        cfg.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr("services.skills.SKILLS_CONFIG", str(cfg))
        assert get_enabled_skills_text() == ""
