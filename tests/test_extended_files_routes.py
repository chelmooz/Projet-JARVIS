"""MT-Lot11-L1R2 — Routes extended_files : authorization (sandbox) requise.

Tests HTTP RED : les 4 routes ``/api/files/{all_drives,mount_ext4,unmount_ext4,
read_ext4_direct}`` doivent exiger le sandbox ``FileSystemService`` (403 sans
autorisation). Le service ``ExtendedFileSystemService`` est mocké via le
singleton module (zéro accès disque réel, zéro PowerShell).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from controllers.router import create_app
from controllers.routes import extended_files as extended_files_routes


class FakeExtendedService:
    """Double du service étendu : réponses déterministes, aucun accès système."""

    def get_all_drives_extended(self) -> dict[str, Any]:
        return {
            "success": True,
            "mounted_drives": [],
            "physical_disks": [],
            "has_ext2fsd": False,
            "ext2fsd_running": False,
            "mounted_ext4": {},
            "platform": "test",
        }

    def mount_ext4_partition(
        self, disk_number: int, partition_number: int, mount_letter: str | None = None
    ) -> dict[str, Any]:
        return {"success": True, "mount_point": "E:\\", "error": None}

    def unmount_ext4_partition(self, disk_number: int, partition_number: int) -> bool:
        return True

    def read_ext4_direct(self, disk_number: int, partition_number: int, target_path: str = "/") -> dict[str, Any]:
        return {"success": True, "entries": [], "total": 0}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App avec le service étendu mocké (singleton module remplacé)."""
    monkeypatch.setattr(extended_files_routes, "_extended_fs_service", FakeExtendedService())
    return TestClient(create_app())


def _without_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retire le sandbox : périmètre d'autorisation non configuré."""
    monkeypatch.delenv("JARVIS_FILES_SANDBOX_ROOT", raising=False)


def test_all_drives_requires_authorization(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_authorization(monkeypatch)
    resp = client.get("/api/files/all_drives")
    assert resp.status_code == 403


def test_mount_ext4_requires_authorization(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_authorization(monkeypatch)
    resp = client.post("/api/files/mount_ext4", json={"disk_number": 1, "partition_number": 2})
    assert resp.status_code == 403


def test_unmount_ext4_requires_authorization(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_authorization(monkeypatch)
    resp = client.post("/api/files/unmount_ext4", json={"disk_number": 1, "partition_number": 2})
    assert resp.status_code == 403


def test_read_ext4_direct_requires_authorization(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _without_authorization(monkeypatch)
    resp = client.post("/api/files/read_ext4_direct", json={"disk_number": 1, "partition_number": 2})
    assert resp.status_code == 403


def test_all_drives_with_authorization_returns_200(client: TestClient, sandbox_root: Any) -> None:
    resp = client.get("/api/files/all_drives")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["mounted_drives"] == []
    assert body["physical_disks"] == []


def test_mount_ext4_with_authorization_returns_200(client: TestClient, sandbox_root: Any) -> None:
    resp = client.post("/api/files/mount_ext4", json={"disk_number": 1, "partition_number": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["mount_point"] == "E:\\"


def test_read_ext4_direct_with_authorization_returns_200(client: TestClient, sandbox_root: Any) -> None:
    resp = client.post("/api/files/read_ext4_direct", json={"disk_number": 1, "partition_number": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["entries"] == []
