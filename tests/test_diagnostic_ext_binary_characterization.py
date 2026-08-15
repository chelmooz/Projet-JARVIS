from __future__ import annotations

import services.diagnostic_ext.binary as binary


def test_resolve_binary_missing_config_and_missing_binary(tmp_path) -> None:
    assert binary.resolve_binary({}, "tool", str(tmp_path)) is None
    config = {"tools": {"tool": {"binary": "tool"}}}
    assert binary.resolve_binary(config, "tool", str(tmp_path)) is None


def test_resolve_binary_linux_prefers_path_then_local(monkeypatch, tmp_path) -> None:
    local = tmp_path / "linux" / "tool"
    local.parent.mkdir()
    local.write_text("binary", encoding="utf-8")
    config = {"tools": {"tool": {"linux_binary": "tool"}}}
    monkeypatch.setattr(binary.sys, "platform", "linux")
    monkeypatch.setattr(binary.shutil, "which", lambda name: None)
    assert binary.resolve_binary(config, "tool", str(tmp_path)) == str(local.resolve())
    monkeypatch.setattr(binary.shutil, "which", lambda name: "/usr/bin/tool")
    monkeypatch.setattr(binary.os.path, "isfile", lambda path: path == "/usr/bin/tool")
    monkeypatch.setattr(binary.os.path, "abspath", lambda path: path)
    assert binary.resolve_binary(config, "tool", str(tmp_path)) == "/usr/bin/tool"


def test_resolve_binary_darwin_and_windows(monkeypatch, tmp_path) -> None:
    config = {"tools": {"tool": {"darwin_binary": "darwin-tool", "binary": "tool.exe"}}}
    monkeypatch.setattr(binary.sys, "platform", "darwin")
    monkeypatch.setattr(binary.shutil, "which", lambda name: None)
    path = tmp_path / "darwin" / "darwin-tool"
    path.parent.mkdir()
    path.write_text("binary", encoding="utf-8")
    assert binary.resolve_binary(config, "tool", str(tmp_path)) == str(path.resolve())
    monkeypatch.setattr(binary.sys, "platform", "win32")
    win = tmp_path / "win" / "tool.exe"
    win.parent.mkdir()
    win.write_text("binary", encoding="utf-8")
    assert binary.resolve_binary(config, "tool", str(tmp_path)) == str(win.resolve())


def test_resolve_binary_no_platform_binary_and_directory_are_rejected(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(binary.sys, "platform", "linux")
    assert binary.resolve_binary({"tools": {"tool": {}}}, "tool", str(tmp_path)) is None
    assert binary.resolve_binary({"tools": {"tool": {"linux_binary": ""}}}, "tool", str(tmp_path)) is None
    directory = tmp_path / "linux" / "tool"
    directory.mkdir(parents=True)
    config = {"tools": {"tool": {"linux_binary": "tool"}}}
    monkeypatch.setattr(binary.shutil, "which", lambda name: None)
    assert binary.resolve_binary(config, "tool", str(tmp_path)) is None


def test_resolve_expected_sha256_variants(monkeypatch) -> None:
    config = {
        "tools": {
            "tool": {
                "sha256": "generic",
                "linux_sha256": "linux",
                "darwin_sha256": "arm",
                "darwin_amd64_sha256": "intel",
            }
        }
    }
    assert binary.resolve_expected_sha256({}, "tool", "linux") == ""
    assert binary.resolve_expected_sha256(config, "tool", "win32") == "generic"
    assert binary.resolve_expected_sha256(config, "tool", "linux") == "linux"
    monkeypatch.setattr(binary._platform, "machine", lambda: "x86_64")
    assert binary.resolve_expected_sha256(config, "tool", "darwin") == "intel"
    monkeypatch.setattr(binary._platform, "machine", lambda: "arm64")
    assert binary.resolve_expected_sha256(config, "tool", "darwin") == "arm"
    assert binary.resolve_expected_sha256({"tools": {"tool": {"sha256": "generic"}}}, "tool", "freebsd") == "generic"
