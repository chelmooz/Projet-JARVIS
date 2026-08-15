import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.file_system import FileSystemError, FileSystemService


@pytest.fixture
def fs(sandbox_root: Path) -> FileSystemService:
    config = sandbox_root / "authorized.json"
    return FileSystemService(config_path=config)


def test_authorize_valid_path(fs: FileSystemService, sandbox_root: Path) -> None:
    target = sandbox_root / "docs"
    target.mkdir()
    assert fs.authorize_path(str(target)) is True
    assert str(target) in fs.list_authorized()


def test_authorize_rejects_traversal(fs: FileSystemService, sandbox_root: Path) -> None:
    assert fs.authorize_path(str(sandbox_root / ".." / "etc")) is False


def test_authorize_rejects_outside_sandbox(fs: FileSystemService, sandbox_root: Path) -> None:
    # Chemin absolu hors sandbox (sur Windows, IS_WINDOWS => garde-fou lecteur désactivé,
    # mais le sandbox rejecte car hors racine).
    assert fs.authorize_path("C:\\Windows") is False


@pytest.mark.skipif(
    os.name != "nt",
    reason="Séparateurs backslash non résolus en chemin par pathlib sous POSIX (Lot 0.3)",
)
def test_authorize_windows_separators(fs: FileSystemService, sandbox_root: Path) -> None:
    target = sandbox_root / "sub"
    target.mkdir()
    backslash = str(target).replace("/", "\\")
    assert fs.authorize_path(backslash) is True


def test_authorize_symlink_outside_skips_if_unprivileged(fs: FileSystemService, sandbox_root: Path) -> None:
    link = sandbox_root / "escape"
    try:
        link.symlink_to(sandbox_root.parent)
    except OSError:
        pytest.skip("symlink indisponible sur cette plateforme")
    assert fs.authorize_path(str(link)) is False


def test_sandbox_missing_raises_file_system_error(fs: FileSystemService) -> None:
    saved = os.environ.pop("JARVIS_FILES_SANDBOX_ROOT", None)
    try:
        with pytest.raises(FileSystemError):
            fs.authorize_path(str(Path(os.getcwd())))
    finally:
        if saved is not None:
            os.environ["JARVIS_FILES_SANDBOX_ROOT"] = saved


def test_read_file_ok(fs: FileSystemService, sandbox_root: Path) -> None:
    d = sandbox_root / "d"
    d.mkdir()
    f = d / "note.txt"
    f.write_text("hello world")
    assert fs.authorize_path(str(d)) is True
    res = fs.read_file(str(f))
    assert res["success"] is True
    assert res["content"] == "hello world"


def test_read_file_rejects_outside(fs: FileSystemService) -> None:
    res = fs.read_file("C:\\Windows")
    assert res["success"] is False
    assert res["error_type"] == "not_authorized"


def test_read_file_too_large_truncated(fs: FileSystemService, sandbox_root: Path) -> None:
    d = sandbox_root / "d"
    d.mkdir()
    f = d / "big.txt"
    f.write_text("x" * 12000)
    assert fs.authorize_path(str(d)) is True
    res = fs.read_file(str(f))
    assert res["success"] is True
    assert "tronqué" in res["content"]


def test_list_dir_ok(fs: FileSystemService, sandbox_root: Path) -> None:
    d = sandbox_root / "d"
    d.mkdir()
    (d / "a.txt").write_text("x")
    (d / "sub").mkdir()
    assert fs.authorize_path(str(d)) is True
    res = fs.list_dir(str(d))
    assert res["success"] is True
    names = {e["name"] for e in res["entries"]}
    assert "a.txt" in names and "sub" in names


def test_revoke_and_is_authorized(fs: FileSystemService, sandbox_root: Path) -> None:
    d = sandbox_root / "d"
    d.mkdir()
    assert fs.authorize_path(str(d)) is True
    assert fs.is_authorized(str(d)) is True
    assert fs.revoke_path(str(d)) is True
    assert fs.is_authorized(str(d)) is False
    assert fs.revoke_path(str(d)) is False


def test_find_files_traversal_rejected(fs: FileSystemService, sandbox_root: Path) -> None:
    res = fs.find_files("../*")
    assert res["success"] is False
    assert res["error_type"] == "not_authorized"


def test_find_files_ok(fs: FileSystemService, sandbox_root: Path) -> None:
    d = sandbox_root / "d"
    d.mkdir()
    (d / "a.log").write_text("x")
    assert fs.authorize_path(str(d)) is True
    res = fs.find_files(str(d / "**" / "*.log"))
    assert res["success"] is True
    assert any("a.log" in m for m in res["matches"])


def test_authorize_empty_string(fs: FileSystemService) -> None:
    assert fs.authorize_path("") is False


def test_read_file_inside_not_authorized(fs: FileSystemService, sandbox_root: Path) -> None:
    f = sandbox_root / "note.txt"
    f.write_text("x")
    res = fs.read_file(str(f))
    assert res["success"] is False
    assert res["error_type"] == "not_authorized"


def test_list_dir_unauthorized(fs: FileSystemService, sandbox_root: Path) -> None:
    res = fs.list_dir(str(sandbox_root))
    assert res["success"] is False
    assert res["error_type"] == "not_authorized"


def test_read_file_on_directory(fs: FileSystemService, sandbox_root: Path) -> None:
    parent = sandbox_root / "d"
    parent.mkdir()
    sub = parent / "sub"
    sub.mkdir()
    assert fs.authorize_path(str(parent)) is True
    res = fs.read_file(str(sub))
    assert res["success"] is False
    assert res["error"] == "Pas un fichier"


def test_load_authorized_invalid_json(sandbox_root: Path) -> None:
    cfg = sandbox_root / "bad.json"
    cfg.write_text("{not valid json")
    svc = FileSystemService(config_path=cfg)
    assert svc.list_authorized() == []


def test_load_authorized_from_existing(sandbox_root: Path) -> None:
    d = sandbox_root / "loaded"
    d.mkdir()
    cfg = sandbox_root / "auth.json"
    escaped = str(d).replace("\\", "\\\\")
    cfg.write_text(f'["{escaped}"]')
    svc = FileSystemService(config_path=cfg)
    assert str(d) in svc.list_authorized()


def test_read_file_binary_decode_error(fs: FileSystemService, sandbox_root: Path) -> None:
    d = sandbox_root / "d"
    d.mkdir()
    f = d / "b.bin"
    f.write_bytes(b"\xff\xfe\x00")
    assert fs.authorize_path(str(d)) is True
    res = fs.read_file(str(f))
    assert res["success"] is False
    assert res["error_type"] == "decode_error"


def test_find_files_truncated(fs: FileSystemService, sandbox_root: Path) -> None:
    d = sandbox_root / "d"
    d.mkdir()
    (d / "a.log").write_text("x")
    (d / "b.log").write_text("x")
    assert fs.authorize_path(str(d)) is True
    res = fs.find_files(str(d / "**" / "*.log"), max_results=1)
    assert res["success"] is True
    assert res["truncated"] is True


@pytest.mark.skipif(
    os.name != "nt",
    reason="Multi-racines Windows (séparateur ';', lecteurs C:/D:) non applicables sous POSIX (Phase 7)",
)
def test_sandbox_multi_root_semicolon(fs: FileSystemService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_FILES_SANDBOX_ROOT", "C:\\;D:\\")
    assert fs.authorize_path(r"D:\data") is True
    assert fs.authorize_path(r"E:\x") is False


def test_sandbox_wildcard(fs: FileSystemService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import psutil

    mounted = tmp_path / "mounted"
    mounted.mkdir()
    monkeypatch.setattr(psutil, "disk_partitions", lambda all=False: [SimpleNamespace(mountpoint=str(mounted))])
    monkeypatch.setenv("JARVIS_FILES_SANDBOX_ROOT", "*")
    assert fs.authorize_path(str(mounted / "data")) is True
    assert fs.authorize_path(str(mounted.parent / "outside")) is False


def test_sandbox_fail_closed_absent(fs: FileSystemService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_FILES_SANDBOX_ROOT", raising=False)
    assert fs.authorize_path(str(Path(os.getcwd()))) is False
    res = fs.list_dir(str(Path(os.getcwd())))
    assert res["success"] is False
    assert res["error_type"] == "not_authorized"
