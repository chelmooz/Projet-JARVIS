from __future__ import annotations

import pytest

import services.diagnostic_ext.config as config
from services.diagnostic_ext.exceptions import DiagnosticExtError


def test_default_smart_device_by_platform(monkeypatch) -> None:
    monkeypatch.setattr(config.sys, "platform", "win32")
    assert config.default_smart_device() == "physicaldrive0"
    monkeypatch.setattr(config.sys, "platform", "darwin")
    assert config.default_smart_device() == "disk0"
    monkeypatch.setattr(config.sys, "platform", "linux")
    assert config.default_smart_device() == "/dev/sda"


def test_load_config_valid_empty_and_non_mapping(tmp_path) -> None:
    valid = tmp_path / "valid.yaml"
    valid.write_text("tools:\n  smartctl: {}\n", encoding="utf-8")
    assert config.load_config(str(valid))["tools"] == {"smartctl": {}}
    empty = tmp_path / "empty.yaml"
    empty.write_text("- item\n", encoding="utf-8")
    assert config.load_config(str(empty)) == {}


def test_load_config_raises_for_missing_and_invalid(tmp_path) -> None:
    with pytest.raises(DiagnosticExtError):
        config.load_config(str(tmp_path / "missing.yaml"))
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("tools: [", encoding="utf-8")
    with pytest.raises(DiagnosticExtError):
        config.load_config(str(invalid))


def test_get_tools_config_accepts_only_mapping() -> None:
    assert config.get_tools_config({"tools": {"x": 1}}) == {"x": 1}
    assert config.get_tools_config({"tools": []}) == {}
    assert config.get_tools_config({}) == {}
