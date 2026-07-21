"""Tests selector — read_preferences, select_model, select_vision_model, recommend_model."""
import json
import os
import sys
from unittest.mock import MagicMock

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.selector import read_preferences, recommend_model, select_model, select_vision_model


class TestModelSizes:
    def test_model_sizes_json_exists_and_valid(self):
        path = os.path.join(_PROJECT_DIR, "config", "model_sizes.json")
        assert os.path.exists(path), "model_sizes.json not found"
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_model_sizes_entries_have_required_fields(self):
        path = os.path.join(_PROJECT_DIR, "config", "model_sizes.json")
        with open(path) as f:
            data = json.load(f)
        required = {"ram_min_gb", "vram_min_gb", "disk_gb", "cpu_only"}
        for name, entry in data.items():
            missing = required - set(entry.keys())
            assert not missing, f"{name} missing fields: {missing}"
            assert isinstance(entry["ram_min_gb"], (int, float))
            assert isinstance(entry["vram_min_gb"], (int, float))
            assert isinstance(entry["disk_gb"], (int, float))
            assert isinstance(entry["cpu_only"], bool)


class TestSelector:

    def test_select_model_returns_empty_when_no_available(self):
        inference = MagicMock()
        inference.resolve_model.return_value = None
        inference.first_available.return_value = None
        result = select_model("dev", inference)
        assert result == ""

    def test_select_vision_model_returns_none_when_no_available(self):
        inference = MagicMock()
        inference.resolve_model.return_value = None
        result = select_vision_model(inference)
        assert result is None

    def test_select_model_uses_first_available_fallback(self):
        inference = MagicMock()
        inference.resolve_model.return_value = "deepseek-coder-v2-lite-instruct:Q4_K_M"
        inference.first_available.return_value = "deepseek-coder-v2-lite-instruct:Q4_K_M"
        result = select_model("dev", inference)
        assert result == "deepseek-coder-v2-lite-instruct:Q4_K_M"

    def test_read_preferences_returns_dict(self):
        prefs = read_preferences()
        assert isinstance(prefs, dict)


class TestRecommendModel:

    def _specs(self, **kwargs):
        defaults = {"ram_gb": 32, "vram_gb": 8, "cpu_only": False}
        defaults.update(kwargs)
        return defaults

    def test_recommend_model_returns_top_match(self):
        specs = self._specs()
        result = recommend_model(specs)
        assert isinstance(result, dict)
        assert "model" in result
        assert result["model"] == "ornith-1.0-9b"

    def test_recommend_model_cpu_only(self):
        specs = self._specs(cpu_only=True, vram_gb=0)
        result = recommend_model(specs)
        assert result["model"] == "phi-4-mini-instruct-abliterated"

    def test_recommend_model_minimal_ram(self):
        specs = self._specs(ram_gb=3, vram_gb=0, cpu_only=True)
        result = recommend_model(specs)
        assert result["model"] == "phi-4-mini-instruct-abliterated"

    def test_oom_guard_excludes_model_when_insufficient_ram(self):
        specs = self._specs(ram_gb=7, vram_gb=0, cpu_only=True)
        result = recommend_model(specs)
        assert result["model"] == "phi-4-mini-instruct-abliterated"

    def test_oom_guard_allows_when_enough_ram(self):
        specs = self._specs(ram_gb=32, vram_gb=8, cpu_only=False)
        result = recommend_model(specs)
        assert result["fallback"] is False
        assert result["model"] == "ornith-1.0-9b"

