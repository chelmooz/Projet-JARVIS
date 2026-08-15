"""ExtendedFileSystemService — Accès étendu aux disques et partitions.

Complète FileSystemService pour détecter et accéder aux disques physiques,
partitions non-montées, et systèmes de fichiers non-Windows.
"""

from __future__ import annotations

import ctypes
import json
import logging
import platform
import re
import string
import subprocess
from pathlib import Path
from typing import Any

import psutil

_logger = logging.getLogger("jarvis.extended_file_system")

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
EXT2FSD_DIR = BIN_DIR / "win" / "ext2fsd"

# Magic bytes pour identification des systèmes de fichiers
FS_SIGNATURES: list[tuple[bytes, str, int]] = [
    (b"\x53\xef", "ext2/ext3/ext4", 1080),
    (b"NXSB", "APFS", 0),
    (b"H+", "HFS+", 1024),
    (b"HX", "HFSX", 1024),
    (b"_BHRfS", "Btrfs", 65600),
    (b"XFSB", "XFS", 0),
    (b"LUKS\xba\xbe", "LUKS (chiffré)", 0),
    (b"VeraCrypt", "VeraCrypt", 0),
    (b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xeb\x52\x90", "NTFS (raw)", 0),
]


class ExtendedFileSystemService:
    """Accès étendu aux disques physiques et partitions non-montées."""

    def __init__(self) -> None:
        self._mounted_ext4: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Détection des disques physiques
    # ------------------------------------------------------------------
    def list_all_physical_disks(self) -> list[dict[str, Any]]:
        """Liste TOUS les disques physiques avec toutes leurs partitions."""
        if platform.system() != "Windows":
            return self._list_disks_linux()
        return self._list_disks_windows()

    def _list_disks_windows(self) -> list[dict[str, Any]]:
        """Liste via PowerShell Get-Disk + Get-Partition."""
        disks: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Disk | Select-Object Number, FriendlyName, Size, PartitionStyle | ConvertTo-Json -Depth 3",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return disks

            disks_data = json.loads(result.stdout)
            if not isinstance(disks_data, list):
                disks_data = [disks_data]

            for disk in disks_data:
                disk_num = disk.get("Number")
                if disk_num is None:
                    continue
                disks.append(
                    {
                        "number": int(disk_num),
                        "name": disk.get("FriendlyName", f"Disque {disk_num}"),
                        "size_bytes": int(disk.get("Size") or 0),
                        "size_gb": round(int(disk.get("Size") or 0) / (1024**3), 2),
                        "style": disk.get("PartitionStyle", "Unknown"),
                        "partitions": self._list_partitions_windows(int(disk_num)),
                    }
                )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as e:
            _logger.warning("Get-Disk a échoué : %s", e)
        return disks

    def _list_partitions_windows(self, disk_number: int) -> list[dict[str, Any]]:
        """Liste toutes les partitions d'un disque (montées ou non)."""
        partitions: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-Partition -DiskNumber {disk_number} | "
                    "Select-Object PartitionNumber, DriveLetter, Size, Type, Offset | "
                    "ConvertTo-Json -Depth 3",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return partitions

            parts_data = json.loads(result.stdout)
            if not isinstance(parts_data, list):
                parts_data = [parts_data]

            for part in parts_data:
                drive_letter = part.get("DriveLetter")
                size_bytes = int(part.get("Size") or 0)
                offset = int(part.get("Offset") or 0)
                part_num = int(part.get("PartitionNumber") or 0)

                fs_type = "Unknown"
                mount_point = None
                if drive_letter:
                    mount_point = f"{drive_letter}:\\"
                    fs_type = self._detect_fs_windows(str(drive_letter))

                # Identification étendue par magic bytes si non montée
                detected_fs = fs_type
                if not drive_letter and size_bytes > 0:
                    detected_fs = self._identify_fs_by_signature(disk_number, offset) or fs_type

                partitions.append(
                    {
                        "number": part_num,
                        "disk": disk_number,
                        "letter": drive_letter,
                        "size_bytes": size_bytes,
                        "size_gb": round(size_bytes / (1024**3), 2),
                        "offset_bytes": offset,
                        "type": part.get("Type", "Unknown"),
                        "filesystem": detected_fs,
                        "mount_point": mount_point,
                        "mounted": drive_letter is not None,
                        "is_linux_fs": detected_fs.lower()
                        in (
                            "ext2",
                            "ext3",
                            "ext4",
                            "ext2/ext3/ext4",
                            "btrfs",
                            "xfs",
                            "reiserfs",
                        ),
                        "is_macos_fs": detected_fs.lower() in ("apfs", "hfs+", "hfsx"),
                        "is_encrypted": detected_fs.lower()
                        in (
                            "luks",
                            "luks (chiffré)",
                            "veracrypt",
                            "bitlocker",
                        ),
                    }
                )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as e:
            _logger.warning("Get-Partition a échoué pour disque %d : %s", disk_number, e)
        return partitions

    def _detect_fs_windows(self, drive_letter: str) -> str:
        """Détecte le FS d'une lettre montée via l'API Win32."""
        try:
            fs_name = ctypes.create_unicode_buffer(256)
            path = f"{drive_letter}:\\"
            ret = ctypes.windll.kernel32.GetVolumeInformationW(path, None, 0, None, None, None, fs_name, 256)
            if ret and fs_name.value:
                return fs_name.value
            return "Unknown"
        except Exception:
            return "Unknown"

    def _identify_fs_by_signature(self, disk_number: int, offset: int) -> str | None:
        """Identifie un FS par lecture des magic bytes sur le disque brut."""
        try:
            raw_path = f"\\\\.\\PhysicalDrive{disk_number}"
            with open(raw_path, "rb") as f:
                header = f.read(max(sig[2] + len(sig[0]) for sig in FS_SIGNATURES) + 64)
        except (PermissionError, FileNotFoundError, OSError) as e:
            _logger.debug("Impossible de lire %s : %s", raw_path, e)
            return None

        for signature, fs_name, sig_offset in FS_SIGNATURES:
            try:
                if header[sig_offset : sig_offset + len(signature)] == signature:
                    return fs_name
            except IndexError:
                continue
        return None

    def _list_disks_linux(self) -> list[dict[str, Any]]:
        """Fallback Linux via lsblk."""
        disks: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                ["lsblk", "-Jb", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,PKNAME"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return disks
            data = json.loads(result.stdout)
            for device in data.get("blockdevices", []):
                if device.get("type") != "disk":
                    continue
                parts = []
                for i, child in enumerate(device.get("children", []), start=1):
                    fst = child.get("fstype") or ""
                    parts.append(
                        {
                            "number": i,
                            "disk": device.get("name"),
                            "size_bytes": int(child.get("size") or 0),
                            "size_gb": round(int(child.get("size") or 0) / (1024**3), 2),
                            "filesystem": fst or "Unknown",
                            "mountpoint": child.get("mountpoint"),
                            "mounted": child.get("mountpoint") is not None,
                            "is_linux_fs": fst in ("ext2", "ext3", "ext4", "btrfs", "xfs"),
                            "is_macos_fs": fst in ("apfs", "hfsplus"),
                            "is_encrypted": "crypto_LUKS" in fst,
                        }
                    )
                disks.append(
                    {
                        "number": device.get("name"),
                        "name": device.get("name"),
                        "size_bytes": int(device.get("size") or 0),
                        "size_gb": round(int(device.get("size") or 0) / (1024**3), 2),
                        "partitions": parts,
                    }
                )
        except Exception as e:
            _logger.warning("lsblk a échoué : %s", e)
        return disks

    # ------------------------------------------------------------------
    # Montage via diskpart + Ext2Fsd service
    # ------------------------------------------------------------------
    def mount_ext4_partition(
        self,
        disk_number: int,
        partition_number: int,
        mount_letter: str | None = None,
    ) -> dict[str, Any]:
        """Monte une partition Linux via diskpart + service Ext2Fsd.

        Prérequis : service Ext2Fsd démarré (Run as Admin sur Ext2Fsd.exe).
        """
        if platform.system() != "Windows":
            return {
                "success": False,
                "mount_point": None,
                "error": "Montage automatique non supporté sous Linux (déjà natif)",
            }

        # Vérifier que le service Ext2Fsd est démarré
        try:
            svc_check = subprocess.run(
                ["sc", "query", "Ext2Fsd"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if "RUNNING" not in svc_check.stdout.upper():
                return {
                    "success": False,
                    "mount_point": None,
                    "error": (
                        "Le service Ext2Fsd n'est pas démarré. "
                        "Cliquez droit sur Ext2Fsd.exe > Exécuter en tant qu'administrateur, "
                        "puis réessayez."
                    ),
                }
        except Exception as e:
            return {
                "success": False,
                "mount_point": None,
                "error": f"Impossible de vérifier Ext2Fsd : {e}",
            }

        if mount_letter is None:
            mount_letter = self._find_free_drive_letter()
            if not mount_letter:
                return {
                    "success": False,
                    "mount_point": None,
                    "error": "Aucune lettre de lecteur libre (E:-Z:)",
                }

        # Assigner la lettre via diskpart
        script = f"select disk {disk_number}\nselect partition {partition_number}\nassign letter={mount_letter}\n"
        try:
            result = subprocess.run(
                ["diskpart"],
                input=script,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            output = (result.stdout or "").lower() + (result.stderr or "").lower()
            if result.returncode != 0 or "successfully" not in output:
                return {
                    "success": False,
                    "mount_point": None,
                    "error": f"diskpart a échoué : {result.stdout or result.stderr}",
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "mount_point": None,
                "error": "Timeout diskpart (>30s)",
            }
        except Exception as e:
            return {"success": False, "mount_point": None, "error": str(e)}

        mount_point = f"{mount_letter}:\\"
        self._mounted_ext4[f"disk{disk_number}_part{partition_number}"] = mount_point
        return {"success": True, "mount_point": mount_point, "error": None}

    def unmount_ext4_partition(self, disk_number: int, partition_number: int) -> bool:
        """Retire la lettre assignée via diskpart."""
        key = f"disk{disk_number}_part{partition_number}"
        if key not in self._mounted_ext4:
            return False
        try:
            script = f"select disk {disk_number}\nselect partition {partition_number}\nremove\n"
            result = subprocess.run(
                ["diskpart"],
                input=script,
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                del self._mounted_ext4[key]
                return True
        except Exception as e:
            _logger.warning("Démontage échoué : %s", e)
        return False

    def unmount_all(self) -> None:
        """Démonte toutes les partitions montées par cette session."""
        for key in list(self._mounted_ext4.keys()):
            match = re.match(r"disk(\d+)_part(\d+)", key)
            if match:
                self.unmount_ext4_partition(int(match.group(1)), int(match.group(2)))

    def _find_free_drive_letter(self) -> str | None:
        """Retourne une lettre E-Z: non utilisée."""
        used = {p[0].upper() for p in self._get_used_drive_letters()}
        for letter in string.ascii_uppercase:
            if letter not in used and letter >= "E":
                return letter
        return None

    def _get_used_drive_letters(self) -> list[str]:
        try:
            return [p.mountpoint for p in psutil.disk_partitions(all=False) if p.mountpoint]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Lecture directe via librairie Python `ext4`
    # ------------------------------------------------------------------
    def read_ext4_direct(
        self,
        disk_number: int,
        partition_number: int,
        target_path: str = "/",
    ) -> dict[str, Any]:
        """Lecture directe d'une partition ext4 via librairie `ext4`.

        Nécessite : pip install ext4
        Nécessite : droits Administrateur (accès raw device).
        """
        try:
            import ext4  # type: ignore[import-not-found]
        except ImportError:
            return {
                "success": False,
                "error": "Librairie `ext4` non installée. Installez : pip install ext4",
            }

        # Récupérer l'offset exact de la partition
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Get-Partition -DiskNumber {disk_number} "
                    f"-PartitionNumber {partition_number} | "
                    "Select-Object -ExpandProperty Offset",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {
                    "success": False,
                    "error": f"Offset introuvable : {result.stderr or 'partition inexistante'}",
                }
            offset = int(result.stdout.strip())
        except (ValueError, subprocess.TimeoutExpired) as e:
            return {"success": False, "error": f"Erreur offset : {e}"}

        raw_path = f"\\\\.\\PhysicalDrive{disk_number}"
        try:
            with open(raw_path, "rb") as f:
                volume = ext4.Volume(f, offset=offset)
                inode = volume.inode_at(target_path)
                if inode.is_dir():
                    entries = []
                    for name, child_inode in inode.items():
                        entries.append(
                            {
                                "name": name,
                                "is_dir": child_inode.is_dir(),
                                "size": int(child_inode.size) if child_inode.is_file() else 0,
                            }
                        )
                    return {"success": True, "entries": entries, "total": len(entries)}
                if inode.is_file():
                    content = inode.read()
                    decoded = content.decode("utf-8", errors="replace")
                    return {
                        "success": True,
                        "content": decoded[:10000],
                        "truncated": len(decoded) > 10000,
                        "size_bytes": len(content),
                    }
                return {
                    "success": False,
                    "error": f"Type inode non supporté : {inode.mode}",
                }
        except PermissionError:
            return {
                "success": False,
                "error": "Permission refusée. Lancez JARVIS en mode Administrateur.",
            }
        except FileNotFoundError:
            return {"success": False, "error": f"Disque introuvable : {raw_path}"}
        except Exception as e:
            _logger.error("Erreur lecture ext4 : %s", e, exc_info=True)
            return {"success": False, "error": f"Erreur lecture ext4 : {e}"}

    # ------------------------------------------------------------------
    # Vue unifiée pour l'API
    # ------------------------------------------------------------------
    def get_all_drives_extended(self) -> dict[str, Any]:
        """Retourne la vue complète (contrat API figé, ne pas modifier)."""
        mounted: list[dict[str, Any]] = []
        try:
            for p in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    mounted.append(
                        {
                            "name": p.mountpoint,
                            "device": p.device,
                            "fstype": p.fstype,
                            "free_gb": round(usage.free / (1024**3), 2),
                            "total_gb": round(usage.total / (1024**3), 2),
                            "mounted": True,
                            "is_linux_fs": False,
                            "is_macos_fs": False,
                            "is_encrypted": False,
                        }
                    )
                except Exception:
                    pass
        except Exception:
            pass

        ext2fsd_available = EXT2FSD_DIR.joinpath("Ext2Fsd.exe").exists()
        if platform.system() == "Windows":
            try:
                svc_check = subprocess.run(
                    ["sc", "query", "Ext2Fsd"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                ext2fsd_running = "RUNNING" in svc_check.stdout.upper()
            except Exception:
                ext2fsd_running = False
        else:
            ext2fsd_running = True

        return {
            "success": True,
            "mounted_drives": mounted,
            "physical_disks": self.list_all_physical_disks(),
            "has_ext2fsd": ext2fsd_available,
            "ext2fsd_running": ext2fsd_running,
            "mounted_ext4": dict(self._mounted_ext4),
            "platform": platform.system(),
        }


__all__ = ["ExtendedFileSystemService"]
