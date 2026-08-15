from __future__ import annotations

import services.embeddable_python as embeddable


def test_pth_file_missing_and_oserror(monkeypatch, tmp_path) -> None:
    assert embeddable._pth_file(str(tmp_path)) is None
    monkeypatch.setattr(embeddable.os, "listdir", lambda path: (_ for _ in ()).throw(OSError("missing")))
    assert embeddable._pth_file(str(tmp_path)) is None


def test_pth_file_finds_matching_entry(tmp_path) -> None:
    (tmp_path / "python._pth").write_text("", encoding="utf-8")
    assert embeddable._pth_file(str(tmp_path)).endswith("python._pth")


def test_is_site_enabled_without_pth_read_error_and_content(tmp_path, monkeypatch) -> None:
    exe = str(tmp_path / "python.exe")
    assert embeddable.is_site_enabled(exe) is True
    pth = tmp_path / "python._pth"
    pth.write_text("#import site\n", encoding="utf-8")
    assert embeddable.is_site_enabled(exe) is False
    pth.write_text("import site\n", encoding="utf-8")
    assert embeddable.is_site_enabled(exe) is True
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read")))
    assert embeddable.is_site_enabled(exe) is True


def test_enable_site_packages_noop_patch_append_and_write_error(tmp_path, monkeypatch) -> None:
    exe = str(tmp_path / "python.exe")
    assert embeddable.enable_site_packages(exe) is True
    pth = tmp_path / "python._pth"
    pth.write_text("#import site\n", encoding="utf-8")
    assert embeddable.enable_site_packages(exe) is True
    assert "import site" in pth.read_text(encoding="utf-8")
    assert embeddable.enable_site_packages(exe) is True
    assert "import site" in pth.read_text(encoding="utf-8")
    pth.write_text("# other\n", encoding="utf-8")
    assert embeddable.enable_site_packages(exe) is True
    assert pth.read_text(encoding="utf-8").endswith("import site\n")
    import builtins

    real_open = builtins.open

    def fail_write(path, mode="r", **kwargs):
        if mode == "w":
            raise OSError("write")
        return real_open(path, mode, **kwargs)

    pth.write_text("# other\n", encoding="utf-8")
    monkeypatch.setattr("builtins.open", fail_write)
    assert embeddable.enable_site_packages(exe) is False


def test_enable_site_packages_read_error(tmp_path, monkeypatch) -> None:
    pth = tmp_path / "python._pth"
    pth.write_text("#import site\n", encoding="utf-8")
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read")))
    assert embeddable.enable_site_packages(str(tmp_path / "python.exe")) is False
