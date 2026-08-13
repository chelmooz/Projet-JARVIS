import os

from services.selector import (
    DEFAULT_FALLBACK_MODEL,
    VISION_OCR_SENTINEL,
    _PreferencesCache,
    fallback_models,
    load_model_sizes,
    read_preferences,
    recommend_model,
    select_model,
    select_vision_analysis_model,
    select_vision_model,
)


def test_fallback_models() -> None:
    fm = fallback_models()
    assert fm["cyber"].startswith("hf.co")
    assert fm["dev"].startswith("hf.co")
    assert fm["vision"] == VISION_OCR_SENTINEL


def test_recommend_model_no_sizes(monkeypatch) -> None:
    monkeypatch.setattr("services.selector.load_model_sizes", lambda: {})
    rec = recommend_model({"ram_gb": 32, "vram_gb": 8, "cpu_only": False})
    assert rec["fallback"] is True
    assert rec["model"] == DEFAULT_FALLBACK_MODEL


def test_recommend_model_picks_heaviest(monkeypatch) -> None:
    sizes = {
        "small": {"ram_min_gb": 4, "vram_min_gb": 0, "cpu_only": False},
        "big": {"ram_min_gb": 16, "vram_min_gb": 0, "cpu_only": False},
    }
    monkeypatch.setattr("services.selector.load_model_sizes", lambda: sizes)
    rec = recommend_model({"ram_gb": 32, "vram_gb": 8, "cpu_only": False})
    assert rec["fallback"] is False
    assert rec["model"] == "big"


def test_recommend_model_cpu_only(monkeypatch) -> None:
    sizes = {
        "gpu_model": {"ram_min_gb": 8, "vram_min_gb": 4, "cpu_only": False},
        "cpu_model": {"ram_min_gb": 8, "vram_min_gb": 0, "cpu_only": True},
    }
    monkeypatch.setattr("services.selector.load_model_sizes", lambda: sizes)
    rec = recommend_model({"ram_gb": 16, "vram_gb": 0, "cpu_only": True})
    assert rec["model"] == "cpu_model"


def test_recommend_model_excludes_cpu_when_gpu(monkeypatch) -> None:
    sizes = {"cpu_model": {"ram_min_gb": 4, "vram_min_gb": 0, "cpu_only": True}}
    monkeypatch.setattr("services.selector.load_model_sizes", lambda: sizes)
    rec = recommend_model({"ram_gb": 32, "vram_gb": 8, "cpu_only": False})
    assert rec["fallback"] is True


def test_select_vision_model_returns_sentinel() -> None:
    assert select_vision_model(None) == VISION_OCR_SENTINEL
    assert select_vision_model(object()) == VISION_OCR_SENTINEL


def test_select_vision_analysis_model_resolved() -> None:
    class FakeInf:
        def resolve_model(self, m: str) -> str:
            return "resolved-model"

    assert select_vision_analysis_model(FakeInf()) == "resolved-model"


def test_select_vision_analysis_model_default() -> None:
    class FakeInf:
        def resolve_model(self, m: str) -> None:
            return None

    assert select_vision_analysis_model(FakeInf()) == DEFAULT_FALLBACK_MODEL


def test_select_model_vision(monkeypatch) -> None:
    monkeypatch.setattr("services.selector.read_preferences", lambda: {})
    assert select_model("vision", None) == VISION_OCR_SENTINEL


def test_select_model_pref_override(monkeypatch) -> None:
    monkeypatch.setattr(
        "services.selector.read_preferences",
        lambda: {"model_map": {"dev": "my-dev-model"}},
    )

    class FakeInf:
        def resolve_model(self, m: str) -> str:
            return m

        def first_available(self) -> str:
            return "generic"

    assert select_model("dev", FakeInf()) == "my-dev-model"


def test_select_model_fallback_agent(monkeypatch) -> None:
    monkeypatch.setattr("services.selector.read_preferences", lambda: {})

    class FakeInf:
        def resolve_model(self, m: str) -> str:
            return m

        def first_available(self) -> str:
            return "generic"

    assert select_model("dev", FakeInf()) == fallback_models()["dev"]


def test_select_model_first_available_logs(monkeypatch) -> None:
    monkeypatch.setattr("services.selector.read_preferences", lambda: {})

    class FakeInf:
        def resolve_model(self, m: str) -> None:
            return None

        def first_available(self) -> str:
            return "generic-model"

    logs: list[str] = []

    class Log:
        def log(self, level: str, msg: str) -> None:
            logs.append(msg)

    assert select_model("dev", FakeInf(), log_service=Log()) == "generic-model"
    assert any("Fallback" in m for m in logs)


def test_select_model_none_available(monkeypatch) -> None:
    monkeypatch.setattr("services.selector.read_preferences", lambda: {})

    class FakeInf:
        def resolve_model(self, m: str) -> None:
            return None

        def first_available(self) -> None:
            return None

    assert select_model("dev", FakeInf()) == ""


def test_recommend_model_ram_too_small(monkeypatch) -> None:
    sizes = {"big": {"ram_min_gb": 64, "vram_min_gb": 0, "cpu_only": False}}
    monkeypatch.setattr("services.selector.load_model_sizes", lambda: sizes)
    rec = recommend_model({"ram_gb": 8, "vram_gb": 8, "cpu_only": False})
    assert rec["fallback"] is True


def test_recommend_model_vram_too_small(monkeypatch) -> None:
    sizes = {"gpu": {"ram_min_gb": 4, "vram_min_gb": 16, "cpu_only": False}}
    monkeypatch.setattr("services.selector.load_model_sizes", lambda: sizes)
    rec = recommend_model({"ram_gb": 64, "vram_gb": 4, "cpu_only": False})
    assert rec["fallback"] is True


def test_recommend_model_skips_embedding(monkeypatch) -> None:
    sizes = {"emb": {"embedding": True, "ram_min_gb": 4}}
    monkeypatch.setattr("services.selector.load_model_sizes", lambda: sizes)
    rec = recommend_model({"ram_gb": 32, "vram_gb": 8, "cpu_only": False})
    assert rec["fallback"] is True


def test_read_preferences_returns_dict() -> None:
    assert isinstance(read_preferences(), dict)


def test_select_model_none_available_logs(monkeypatch) -> None:
    monkeypatch.setattr("services.selector.read_preferences", lambda: {})

    class FakeInf:
        def resolve_model(self, m: str) -> None:
            return None

        def first_available(self) -> None:
            return None

    logs: list[str] = []

    class Log:
        def log(self, level: str, msg: str) -> None:
            logs.append(msg)

    assert select_model("dev", FakeInf(), log_service=Log()) == ""
    assert any("Aucun modèle" in m for m in logs)


def test_load_model_sizes(tmp_path, monkeypatch) -> None:
    p = tmp_path / "sizes.json"
    p.write_text('{"a": {"ram_min_gb": 4}}')
    monkeypatch.setattr("services.selector.MODEL_SIZES_PATH", str(p))
    assert load_model_sizes() == {"a": {"ram_min_gb": 4}}


def test_load_model_sizes_corrupt(tmp_path, monkeypatch) -> None:
    p = tmp_path / "sizes.json"
    p.write_text("{bad")
    monkeypatch.setattr("services.selector.MODEL_SIZES_PATH", str(p))
    assert load_model_sizes() == {}


def test_preferences_cache_missing_file(tmp_path) -> None:
    cache = _PreferencesCache(str(tmp_path / "nope.json"))
    assert cache.get() == {}


def test_preferences_cache_corrupt(tmp_path) -> None:
    p = tmp_path / "prefs.json"
    p.write_text("{bad")
    cache = _PreferencesCache(str(p))
    assert cache.get() == {}


def test_preferences_cache_reloads_on_change(tmp_path, monkeypatch) -> None:
    p = tmp_path / "prefs.json"
    p.write_text('{"model_map": {"dev": "x"}}')
    # mtime déterministe (le FS de test a une résolution à la seconde)
    mtimes = iter([100.0, 200.0])
    monkeypatch.setattr(os.path, "getmtime", lambda _path: next(mtimes))
    cache = _PreferencesCache(str(p))
    assert cache.get() == {"model_map": {"dev": "x"}}
    p.write_text('{"model_map": {"dev": "y"}}')
    assert cache.get() == {"model_map": {"dev": "y"}}
