"""Tests checks — warn_low_memory (psutil déjà présent, item audit RAM)."""
import services.diagnostics.checks as checks


def test_warn_low_memory_triggers_when_low(monkeypatch):
    monkeypatch.setattr(checks, "check_ram", lambda: {"available_gb": 1.0})
    result = checks.warn_low_memory(threshold_gb=2.0)
    assert result is not None
    assert result["level"] == "warning"


def test_warn_low_memory_none_when_sufficient(monkeypatch):
    monkeypatch.setattr(checks, "check_ram", lambda: {"available_gb": 8.0})
    assert checks.warn_low_memory(threshold_gb=2.0) is None
