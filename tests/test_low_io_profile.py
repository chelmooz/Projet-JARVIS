"""TDD — Profil low I/O / low VRAM (M23b)."""
import importlib
import sys


def _fresh_constants():
    """Recharge config.constants proprement (gère les tests qui l'auraient viré de sys.modules)."""
    if "config.constants" in sys.modules:
        del sys.modules["config.constants"]
    import config.constants
    return config.constants


def test_low_io_env_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JARVIS_LOW_IO", raising=False)
    constants = _fresh_constants()
    assert constants.JARVIS_LOW_IO is False
    assert constants.vector_cache_size() == constants.VECTOR_CACHE_SIZE_NORMAL
    assert constants.default_top_k() == constants.DEFAULT_TOP_K


def test_low_io_env_enabled_reduces_sizes(monkeypatch):
    monkeypatch.setenv("JARVIS_LOW_IO", "1")
    constants = _fresh_constants()
    assert constants.JARVIS_LOW_IO is True
    assert constants.vector_cache_size() == constants.VECTOR_CACHE_SIZE_LOW
    assert constants.default_top_k() == constants.DEFAULT_TOP_K_LOW
    assert constants.vector_cache_size() < constants.VECTOR_CACHE_SIZE_NORMAL


def test_vector_cache_default_uses_profile(monkeypatch):
    monkeypatch.setenv("JARVIS_LOW_IO", "1")
    constants = _fresh_constants()
    import importlib
    import services.vector_cache as vc_mod
    importlib.reload(vc_mod)
    cache = vc_mod.VectorCache()
    assert cache._max_size == constants.VECTOR_CACHE_SIZE_LOW
