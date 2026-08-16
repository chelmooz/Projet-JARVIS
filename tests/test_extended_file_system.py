"""Tests de ExtendedFileSystemService (services/extended_file_system.py).

MT-Lot11-L1R1 : rétrofit de couverture — tests unitaires avec mocks
subprocess/psutil/ctypes/open, zéro accès disque réel ni PowerShell.
"""

from __future__ import annotations

import ctypes
import sys
from types import SimpleNamespace
from typing import Any

import pytest

import services.extended_file_system as fs_module
from services.extended_file_system import ExtendedFileSystemService

DISK_JSON = '[{"Number": 1, "FriendlyName": "Disque 1", "Size": 1073741824, "PartitionStyle": "GPT"}]'


class FakeFile:
    """Fichier binaire factice, compatible context manager (``with open(...) as f``)."""

    def __init__(self, data: bytes = b"") -> None:
        self._data = data

    def __enter__(self) -> FakeFile:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False

    def read(self, n: int | None = None) -> bytes:
        return self._data[:n] if n is not None else self._data


@pytest.fixture
def svc() -> ExtendedFileSystemService:
    return ExtendedFileSystemService()


@pytest.fixture
def windows_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fs_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(fs_module.subprocess, "CREATE_NO_WINDOW", 0, raising=False)


def test_list_all_physical_disks_calls_get_disk(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append(args)
        if "Get-Disk" in " ".join(args):
            return SimpleNamespace(returncode=0, stdout=DISK_JSON)
        return SimpleNamespace(returncode=0, stdout="[]")

    monkeypatch.setattr(fs_module.subprocess, "run", fake_run)

    disks = svc.list_all_physical_disks()

    assert any("Get-Disk" in " ".join(c) for c in calls)
    assert disks == [
        {
            "number": 1,
            "name": "Disque 1",
            "size_bytes": 1073741824,
            "size_gb": 1.0,
            "style": "GPT",
            "partitions": [],
        }
    ]


def test_list_all_physical_disks_returns_disks_with_partitions(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    partitions = [
        {
            "number": 1,
            "letter": "C",
            "size_bytes": 536870912,
            "offset_bytes": 1048576,
            "filesystem": "NTFS",
            "mounted": True,
        },
        {
            "number": 2,
            "letter": None,
            "size_bytes": 268435456,
            "offset_bytes": 2097152,
            "filesystem": "ext4",
            "mounted": False,
        },
    ]
    monkeypatch.setattr(svc, "_list_partitions_windows", lambda n: partitions)
    monkeypatch.setattr(fs_module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=DISK_JSON))

    disks = svc.list_all_physical_disks()

    assert len(disks) == 1
    assert disks[0]["number"] == 1
    assert disks[0]["partitions"] == partitions


def test_list_partitions_windows_calls_get_partition(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="[]")

    monkeypatch.setattr(fs_module.subprocess, "run", fake_run)

    result = svc._list_partitions_windows(1)

    assert result == []
    assert any("Get-Partition -DiskNumber 1" in " ".join(c) for c in calls)


def test_detect_fs_windows_calls_get_volume_information(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_get_volume_information(
        path: Any, _a: Any, _b: Any, _c: Any, _d: Any, _e: Any, fs_name: Any, _size: Any
    ) -> int:
        calls.append(path)
        fs_name.value = "NTFS"
        return 1

    fake_windll = SimpleNamespace(kernel32=SimpleNamespace(GetVolumeInformationW=fake_get_volume_information))
    monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)

    assert svc._detect_fs_windows("C") == "NTFS"
    assert calls == ["C:\\"]


def test_identify_fs_by_signature_reads_raw_disk(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    header = bytearray(max(sig[2] + len(sig[0]) for sig in fs_module.FS_SIGNATURES) + 64)
    header[1080:1082] = b"\x53\xef"

    def fake_open(path: str, mode: str = "rb") -> FakeFile:
        opened.append(path)
        return FakeFile(bytes(header))

    monkeypatch.setattr("builtins.open", fake_open)

    assert svc._identify_fs_by_signature(0, 1048576) == "ext2/ext3/ext4"
    assert opened == ["\\\\.\\PhysicalDrive0"]


def test_mount_ext4_partition_checks_service_running(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    monkeypatch.setattr(
        fs_module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="STATE : 1 STOPPED")
    )

    result = svc.mount_ext4_partition(1, 2)

    assert result["success"] is False
    assert "Ext2Fsd" in result["error"]


def test_mount_ext4_partition_assigns_letter_via_diskpart(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    scripts: list[str] = []

    def fake_run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        if "Get-Partition -DriveLetter" in " ".join(args):
            return SimpleNamespace(returncode=0, stdout="0")
        if "sc" in args:
            return SimpleNamespace(returncode=0, stdout="STATE : 4 RUNNING")
        scripts.append(kwargs.get("input", ""))
        return SimpleNamespace(
            returncode=0,
            stdout="DiskPart successfully assigned the drive letter or mount point.",
            stderr="",
        )

    monkeypatch.setattr(fs_module.subprocess, "run", fake_run)

    result = svc.mount_ext4_partition(1, 2, "E")

    assert result == {"success": True, "mount_point": "E:\\", "error": None}
    assert scripts == ["select disk 1\nselect partition 2\nassign letter=E\n"]
    assert svc._mounted_ext4 == {"disk1_part2": "E:\\"}


def test_mount_ext4_partition_rejects_system_disk(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    system_calls: list[str] = []

    def fake_run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        cmd = " ".join(args)
        if "Get-Partition -DriveLetter" in cmd:
            system_calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout="1")
        if "sc" in args:
            return SimpleNamespace(returncode=0, stdout="STATE : 4 RUNNING")
        return SimpleNamespace(
            returncode=0,
            stdout="DiskPart successfully assigned the drive letter or mount point.",
            stderr="",
        )

    monkeypatch.setattr(fs_module.subprocess, "run", fake_run)

    result = svc.mount_ext4_partition(1, 2, "E")

    assert result["success"] is False
    assert "système" in result["error"]
    assert svc._mounted_ext4 == {}
    assert any("Get-Partition -DriveLetter" in c and "Get-Disk" in c for c in system_calls)


def test_mount_ext4_partition_allows_non_system_disk(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    def fake_run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        cmd = " ".join(args)
        if "Get-Partition -DriveLetter" in cmd:
            return SimpleNamespace(returncode=0, stdout="0")
        if "sc" in args:
            return SimpleNamespace(returncode=0, stdout="STATE : 4 RUNNING")
        return SimpleNamespace(
            returncode=0,
            stdout="DiskPart successfully assigned the drive letter or mount point.",
            stderr="",
        )

    monkeypatch.setattr(fs_module.subprocess, "run", fake_run)

    result = svc.mount_ext4_partition(1, 2, "E")

    assert result["success"] is True
    assert result["mount_point"] == "E:\\"


def test_mount_ext4_partition_system_disk_detection_failure_falls_through(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    def fake_run(args: list[str], **kwargs: Any) -> SimpleNamespace:
        cmd = " ".join(args)
        if "Get-Partition -DriveLetter" in cmd:
            return SimpleNamespace(returncode=0, stdout="not-a-number")
        if "sc" in args:
            return SimpleNamespace(returncode=0, stdout="STATE : 1 STOPPED")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(fs_module.subprocess, "run", fake_run)

    result = svc.mount_ext4_partition(1, 2, "E")

    assert result["success"] is False
    assert "Ext2Fsd" in result["error"]


def test_read_ext4_direct_uses_correct_offset(svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_EXT4_WHITELIST", "1")
    volume_calls: list[tuple[Any, int]] = []

    class FakeVolume:
        def __init__(self, f: Any, offset: int) -> None:
            volume_calls.append((f, offset))

        def inode_at(self, path: str) -> SimpleNamespace:
            child = SimpleNamespace(is_dir=lambda: False, is_file=lambda: True, size=5)
            return SimpleNamespace(is_dir=lambda: True, is_file=lambda: False, items=lambda: iter([("a.txt", child)]))

    monkeypatch.setitem(sys.modules, "ext4", SimpleNamespace(Volume=FakeVolume))
    monkeypatch.setattr(fs_module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="1048576"))
    monkeypatch.setattr("builtins.open", lambda path, mode="rb": FakeFile())

    result = svc.read_ext4_direct(1, 2, "/")

    assert result["success"] is True
    assert result["total"] == 1
    assert result["entries"] == [{"name": "a.txt", "is_dir": False, "size": 5}]
    assert len(volume_calls) == 1
    assert volume_calls[0][1] == 1048576


def test_read_ext4_direct_whitelist_absente_refus(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.delenv("JARVIS_EXT4_WHITELIST", raising=False)
    monkeypatch.setattr(svc, "_open_raw_disk", lambda path: opened.append(path) or FakeFile())

    result = svc.read_ext4_direct(1, 1)

    assert result["success"] is False
    assert "whitelist" in result["error"] or "autoris" in result["error"]
    assert opened == []


def test_read_ext4_direct_disk_non_whiteliste_refus(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_EXT4_WHITELIST", "0")

    result = svc.read_ext4_direct(1, 1)

    assert result["success"] is False
    assert "whitelist" in result["error"] or "autoris" in result["error"]


def test_read_ext4_direct_disk_whiteliste_succee(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_EXT4_WHITELIST", "0,1")

    class FakeVolume:
        def __init__(self, f: Any, offset: int) -> None:
            pass

        def inode_at(self, path: str) -> SimpleNamespace:
            child = SimpleNamespace(is_dir=lambda: False, is_file=lambda: True, size=5)
            return SimpleNamespace(is_dir=lambda: True, is_file=lambda: False, items=lambda: iter([("a.txt", child)]))

    monkeypatch.setitem(sys.modules, "ext4", SimpleNamespace(Volume=FakeVolume))
    monkeypatch.setattr(fs_module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="1048576"))
    monkeypatch.setattr(svc, "_open_raw_disk", lambda path: FakeFile())

    result = svc.read_ext4_direct(1, 1, "/")

    assert result["success"] is True
    assert result["entries"] == [{"name": "a.txt", "is_dir": False, "size": 5}]


def test_get_all_drives_extended_returns_contract(
    svc: ExtendedFileSystemService, monkeypatch: pytest.MonkeyPatch, windows_env: None
) -> None:
    monkeypatch.setattr(fs_module.psutil, "disk_partitions", lambda all=False: [])
    monkeypatch.setattr(svc, "list_all_physical_disks", lambda: [])
    monkeypatch.setattr(
        fs_module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="STATE : 4 RUNNING")
    )
    monkeypatch.setattr(
        fs_module, "EXT2FSD_DIR", SimpleNamespace(joinpath=lambda name: SimpleNamespace(exists=lambda: False))
    )

    result = svc.get_all_drives_extended()

    assert set(result) == {
        "success",
        "mounted_drives",
        "physical_disks",
        "has_ext2fsd",
        "ext2fsd_running",
        "mounted_ext4",
        "platform",
    }
    assert result["success"] is True
    assert result["mounted_drives"] == []
    assert result["physical_disks"] == []
    assert result["has_ext2fsd"] is False
    assert result["ext2fsd_running"] is True
    assert result["mounted_ext4"] == {}
    assert result["platform"] == "Windows"
