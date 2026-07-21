"""TDD — Profil low I/O / low VRAM (M23b)."""
import importlib

import config.constants as constants


def test_low_io_env_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_LOW_IO", raising=False)
    importlib.reload(constants)
    assert constants.JARVIS_LOW_IO is False
    assert constants.vector_cache_size() == constants.VECTOR_CACHE_SIZE_NORMAL
    assert constants.default_top_k() == constants.DEFAULT_TOP_K


def test_low_io_env_enabled_reduces_sizes(monkeypatch):
    monkeypatch.setenv("JARVIS_LOW_IO", "1")
    importlib.reload(constants)
    assert constants.JARVIS_LOW_IO is True
    assert constants.vector_cache_size() == constants.VECTOR_CACHE_SIZE_LOW
    assert constants.default_top_k() == constants.DEFAULT_TOP_K_LOW
    assert constants.vector_cache_size() < constants.VECTOR_CACHE_SIZE_NORMAL


def test_vector_cache_default_uses_profile(monkeypatch):
    monkeypatch.setenv("JARVIS_LOW_IO", "1")
    importlib.reload(constants)
    from services.vector_cache import VectorCache

    cache = VectorCache()
    assert cache._max_size == constants.VECTOR_CACHE_SIZE_LOW
