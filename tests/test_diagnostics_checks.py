from __future__ import annotations

from types import SimpleNamespace

import services.diagnostics.checks as checks


def test_check_os_uses_freedesktop_release(monkeypatch) -> None:
    monkeypatch.setattr(checks.platform, "uname", lambda: SimpleNamespace(machine="x86", node="host", release="r"))
    monkeypatch.setattr(checks.platform, "platform", lambda: "fallback")
    monkeypatch.setattr(checks.platform, "system", lambda: "Linux")
    monkeypatch.setattr(checks.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": "24"})
    assert checks.check_os() == {"os": "linux", "dist": "ubuntu 24", "arch": "x86", "hostname": "host", "kernel": "r"}


def test_check_os_falls_back_when_release_fails(monkeypatch) -> None:
    monkeypatch.setattr(checks.platform, "uname", lambda: SimpleNamespace(machine="x", node="h", release="r"))
    monkeypatch.setattr(checks.platform, "platform", lambda: "fallback")
    monkeypatch.setattr(checks.platform, "system", lambda: "Test")

    def fail():
        raise OSError("no release")

    monkeypatch.setattr(checks.platform, "freedesktop_os_release", fail)
    assert checks.check_os()["dist"] == "fallback"


def test_check_cpu_reads_proc_cpuinfo(monkeypatch) -> None:
    class FakeFile:
        def __enter__(self):
            return iter(["model name : Test CPU\n"])

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: FakeFile())
    monkeypatch.setattr(checks.platform, "machine", lambda: "amd64")
    monkeypatch.setattr(checks.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(checks.psutil, "cpu_count", lambda logical=False: 4)
    monkeypatch.setattr(checks.psutil, "cpu_percent", lambda interval: 12.5)
    result = checks.check_cpu()
    assert result["model"] == "Test CPU"
    assert result["cores_logical"] == 8
    assert result["cores_physical"] == 4
    assert result["load_percent"] == 12.5


def test_check_cpu_uses_apple_brand_when_proc_missing(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise OSError("missing")

    monkeypatch.setattr("builtins.open", fail)
    monkeypatch.setattr(checks, "_apple_cpu_brand", lambda: "Apple CPU")
    monkeypatch.setattr(checks.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(checks.sys, "platform", "darwin")
    monkeypatch.setattr(checks.os, "cpu_count", lambda: None)
    monkeypatch.setattr(checks.psutil, "cpu_count", lambda logical=False: None)
    monkeypatch.setattr(checks.psutil, "cpu_percent", lambda interval: 0.0)
    result = checks.check_cpu()
    assert result["model"] == "Apple CPU"
    assert result["apple_silicon"] is True
    assert result["cores_logical"] == 0


def test_apple_cpu_brand_success_and_failure(monkeypatch) -> None:
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=" M1 \n"))
    assert checks._apple_cpu_brand() == "M1"

    def fail(*args, **kwargs):
        raise RuntimeError("sysctl")

    monkeypatch.setattr(checks.subprocess, "run", fail)
    assert checks._apple_cpu_brand() == ""


def test_check_ram_and_warn_low_memory(monkeypatch) -> None:
    monkeypatch.setattr(
        checks.psutil, "virtual_memory", lambda: SimpleNamespace(total=4 * 1024**3, available=1 * 1024**3, percent=75)
    )
    monkeypatch.setattr(checks.psutil, "swap_memory", lambda: SimpleNamespace(total=2 * 1024**3))
    assert checks.check_ram() == {"total_gb": 4.0, "available_gb": 1.0, "used_percent": 75.0, "swap_gb": 2.0}
    assert checks.warn_low_memory(2.0) == {"level": "warning", "available_gb": 1.0, "threshold_gb": 2.0}
    monkeypatch.setattr(checks, "check_ram", lambda: {"available_gb": 3.0})
    assert checks.warn_low_memory(2.0) is None


def test_detect_gpu_success_failure_and_exception(monkeypatch) -> None:
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="gpu"))
    assert checks._detect_gpu(["cmd"], "vendor", str)["detail"] == "gpu"
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="gpu"))
    assert checks._detect_gpu(["cmd"], "vendor", str) is None

    def fail(*args, **kwargs):
        raise OSError("cmd")

    monkeypatch.setattr(checks.subprocess, "run", fail)
    assert checks._detect_gpu(["cmd"], "vendor", str) is None


def test_parse_nvidia_vram_mib_gib_and_invalid() -> None:
    assert checks._parse_nvidia_vram("GPU, 2048 MiB") == 2.0
    assert checks._parse_nvidia_vram("GPU, 4 GiB") == 4.0
    assert checks._parse_nvidia_vram("GPU, bad MiB\n\ninvalid") == 0.0


def test_check_gpu_nvidia(monkeypatch) -> None:
    responses = iter(
        [
            SimpleNamespace(returncode=0, stdout="RTX 4090, 24576 MiB"),
            SimpleNamespace(returncode=0, stdout="GPU, 24576 MiB"),
        ]
    )
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: next(responses))
    result = checks.check_gpu()
    assert result == {"detected": True, "vendor": "nvidia", "detail": "RTX 4090, 24576 MiB", "vram_gb": 24.0}


def test_check_gpu_nvidia_handles_vram_error(monkeypatch) -> None:
    monkeypatch.setattr(checks, "_detect_gpu", lambda *args: {"detected": True, "vendor": "nvidia", "detail": "GPU"})

    def fail(*args, **kwargs):
        raise OSError("vram")

    monkeypatch.setattr(checks.subprocess, "run", fail)
    assert checks.check_gpu()["vram_gb"] == 0.0


def test_check_gpu_amd_and_none(monkeypatch) -> None:
    monkeypatch.setattr(
        checks,
        "_detect_gpu",
        lambda cmd, vendor, detail: {"detected": True, "vendor": vendor, "detail": "AMD"} if vendor == "amd" else None,
    )
    assert checks.check_gpu() == {"detected": True, "vendor": "amd", "detail": "AMD", "vram_gb": 0.0}
    monkeypatch.setattr(checks, "_detect_gpu", lambda *args: None)
    monkeypatch.setattr(checks.sys, "platform", "linux")
    assert checks.check_gpu()["detected"] is False


def test_check_gpu_apple(monkeypatch) -> None:
    monkeypatch.setattr(checks, "_detect_gpu", lambda *args: None)
    monkeypatch.setattr(checks.sys, "platform", "darwin")
    monkeypatch.setattr(checks, "_apple_cpu_brand", lambda: "M2")
    assert checks.check_gpu()["vendor"] == "apple"


def test_check_python_reports_missing_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(checks.sys, "prefix", "/venv")
    monkeypatch.setattr(checks.sys, "base_prefix", "/python")
    monkeypatch.setattr(checks.sys, "platform", "linux")
    monkeypatch.setattr(checks.os.path, "exists", lambda path: path.endswith("python"))
    monkeypatch.setattr(checks, "find_python", lambda: "/other/python")

    def fake_import(name, *args, **kwargs):
        if name in {"numpy", "httpx"}:
            raise ImportError(name)
        return object()

    monkeypatch.setattr(checks, "__import__", fake_import, raising=False)
    result = checks.check_python()
    assert result["in_venv"] is True
    assert result["venv_ok"] is True
    assert result["portable_ok"] is False
    assert result["missing_deps"] == ["numpy", "httpx"]
    monkeypatch.setattr(checks.sys, "platform", "win32")
    assert checks.check_python()["selected_python"] == "/other/python"


def test_check_binaries_with_file_and_errors(monkeypatch, tmp_path) -> None:
    binary = tmp_path / "ollama"
    binary.write_text("bin", encoding="utf-8")
    monkeypatch.setattr(checks, "get_ollama_path", lambda: str(binary))
    monkeypatch.setattr(checks.sys, "platform", "linux")
    monkeypatch.setattr(checks.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="ELF"))
    assert checks.check_binaries()[0]["file_info"] == "ELF"

    def fail(*args, **kwargs):
        raise OSError("file")

    monkeypatch.setattr(checks.subprocess, "run", fail)
    assert checks.check_binaries()[0]["file_info"] is None
    monkeypatch.setattr(checks, "get_ollama_path", lambda: None)
    assert checks.check_binaries()[0]["exists"] is False


def test_check_network_reports_ports_and_internet(monkeypatch) -> None:
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, value):
            self.timeout = value

        def connect_ex(self, address):
            return 0 if address[1] == next(iter(checks.PORTS)) else 1

    monkeypatch.setattr(checks.socket, "socket", lambda *args: FakeSocket())
    monkeypatch.setattr(checks.urllib.request, "urlopen", lambda *args, **kwargs: object())
    result = checks.check_network()
    assert result["internet"] is True
    assert result["ports"][str(next(iter(checks.PORTS)))] == "in_use"
    monkeypatch.setattr(
        checks.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline"))
    )
    assert checks.check_network()["internet"] is False


def test_check_disk_calculates_mount_and_zero_usage(monkeypatch) -> None:
    monkeypatch.setattr(checks.shutil, "disk_usage", lambda path: SimpleNamespace(total=0, free=0, used=0))
    monkeypatch.setattr(checks.os.path, "ismount", lambda path: True)
    result = checks.check_disk()
    assert result["used_percent"] == 0.0
    assert result["mount_point"] == str(checks.PROJECT_DIR)


def test_check_disk_walks_to_mount(monkeypatch) -> None:
    monkeypatch.setattr(checks.shutil, "disk_usage", lambda path: SimpleNamespace(total=100, free=25, used=75))
    monkeypatch.setattr(checks, "PROJECT_DIR", "/a/b")
    monkeypatch.setattr(checks.os.path, "ismount", lambda path: path == "/")
    monkeypatch.setattr(checks.os.path, "dirname", lambda path: {"/a/b": "/a", "/a": "/", "/": "/"}[path])
    result = checks.check_disk()
    assert result["mount_point"] == "/"
    assert result["used_percent"] == 75.0


def test_check_disk_breaks_when_parent_equals_mount(monkeypatch) -> None:
    monkeypatch.setattr(checks.shutil, "disk_usage", lambda path: SimpleNamespace(total=10, free=5, used=5))
    monkeypatch.setattr(checks, "PROJECT_DIR", "/root")
    monkeypatch.setattr(checks.os.path, "ismount", lambda path: False)
    monkeypatch.setattr(checks.os.path, "dirname", lambda path: path)
    assert checks.check_disk()["mount_point"] == "/root"
