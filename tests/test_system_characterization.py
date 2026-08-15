from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import services.system as system


def test_venv_python_and_portable_candidates_by_platform(monkeypatch) -> None:
    monkeypatch.setattr(system, "VENV_DIR", "/venv")
    monkeypatch.setattr(system, "SYSTEM", "windows")
    assert system._venv_python() == system.os.path.join("/venv", "Scripts", "python.exe")
    assert len(system._portable_candidates()) == 2
    monkeypatch.setattr(system, "SYSTEM", "darwin")
    assert system._portable_candidates()[1].name == "python3"
    monkeypatch.setattr(system, "SYSTEM", "linux")
    assert system._portable_candidates()[1].name == "python3"
    assert system._portable_candidates()[1].parent.name == "bin"


def test_find_python_prefers_first_existing_candidate(monkeypatch) -> None:
    portable = Path("portable")
    other = Path("other")
    monkeypatch.setattr(system, "_portable_candidates", lambda: [portable, other])
    monkeypatch.setattr(system, "_venv_python", lambda: "venv-python")
    monkeypatch.setattr(system.os.path, "exists", lambda path: Path(path).name == other.name)
    monkeypatch.setattr(system, "PYTHON", "system-python")
    assert system.find_python() == str(other)
    monkeypatch.setattr(system.os.path, "exists", lambda path: False)
    assert system.find_python() == "system-python"


def test_is_embeddable_success_failure_and_oserror(monkeypatch) -> None:
    monkeypatch.setattr(system.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    assert system._is_embeddable("python") is False
    monkeypatch.setattr(system.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1))
    assert system._is_embeddable("python") is True

    def fail(*args, **kwargs):
        raise OSError("missing")

    monkeypatch.setattr(system.subprocess, "run", fail)
    assert system._is_embeddable("python") is True


def test_install_deps_success_failure_and_upgrade_error(monkeypatch) -> None:
    calls = []
    responses = iter([SimpleNamespace(returncode=0), SimpleNamespace(returncode=0, stderr="")])
    monkeypatch.setattr(system.subprocess, "run", lambda *args, **kwargs: calls.append(args[0]) or next(responses))
    logs = []
    assert system._install_deps("python", "/project", lambda *args: logs.append(args)) is True
    assert logs[-1] == ("Setup", "OK", True)
    responses = iter([SimpleNamespace(returncode=0), SimpleNamespace(returncode=1, stderr="bad")])
    assert system._install_deps("python", "/project", lambda *args: logs.append(args)) is False

    def fail(*args, **kwargs):
        raise OSError("upgrade")

    def upgrade_then_fail(*args, **kwargs):
        if "--upgrade" in args[0]:
            raise OSError("upgrade")
        raise OSError("install")

    monkeypatch.setattr(system.subprocess, "run", upgrade_then_fail)
    with pytest.raises(OSError, match="install"):
        system._install_deps("python", "/project", lambda *args: logs.append(args))


def test_ensure_venv_portable_site_activation(monkeypatch) -> None:
    logs = []
    monkeypatch.setattr(system, "find_python", lambda: "/portable/python")
    monkeypatch.setattr(system, "_portable_candidates", lambda: [Path("/portable/python")])
    monkeypatch.setattr(system, "_is_embeddable", lambda _: True)
    monkeypatch.setattr(system, "is_site_enabled", lambda _: False)
    monkeypatch.setattr(system, "enable_site_packages", lambda _: True)
    monkeypatch.setattr(system.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    assert system.ensure_venv(lambda *args: logs.append(args)) == ("/portable/python", True)
    assert any("redémarrage requis" in item[1] for item in logs)


def test_ensure_venv_portable_activation_failure_and_import_install(monkeypatch) -> None:
    logs = []
    monkeypatch.setattr(system, "find_python", lambda: "/portable/python")
    monkeypatch.setattr(system, "_portable_candidates", lambda: [Path("/portable/python")])
    monkeypatch.setattr(system, "_is_embeddable", lambda _: True)
    monkeypatch.setattr(system, "is_site_enabled", lambda _: False)
    monkeypatch.setattr(system, "enable_site_packages", lambda _: False)
    monkeypatch.setattr(
        system.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="missing")
    )
    monkeypatch.setattr(system, "_install_deps", lambda *args: True)
    result = system.ensure_venv(lambda *args: logs.append(args))
    assert result == ("/portable/python", False)
    assert any(item[2] is False for item in logs)


def test_ensure_venv_creates_venv_and_installs(monkeypatch, tmp_path) -> None:
    logs = []
    target = str(tmp_path / "venv" / "bin" / "python")
    monkeypatch.setattr(system, "find_python", lambda: "/system/python")
    monkeypatch.setattr(system, "_portable_candidates", lambda: [])
    monkeypatch.setattr(system, "_is_embeddable", lambda _: False)
    monkeypatch.setattr(system, "_venv_python", lambda: target)
    monkeypatch.setattr(system.os.path, "exists", lambda path: path.endswith("python") and path == target)
    monkeypatch.setattr(system.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr=""))
    result = system.ensure_venv(lambda *args: logs.append(args))
    assert result == (target, False)


def test_ensure_venv_handles_venv_oserror_and_nonzero(monkeypatch) -> None:
    logs = []
    monkeypatch.setattr(system, "find_python", lambda: "/system/python")
    monkeypatch.setattr(system, "_portable_candidates", lambda: [])
    monkeypatch.setattr(system, "_is_embeddable", lambda _: False)
    monkeypatch.setattr(system, "_venv_python", lambda: "/venv/python")
    monkeypatch.setattr(system.os.path, "exists", lambda path: False)

    def fail(*args, **kwargs):
        raise OSError("bad python")

    monkeypatch.setattr(system.subprocess, "run", fail)
    assert system.ensure_venv(lambda *args: logs.append(args)) == ("/system/python", False)
    monkeypatch.setattr(
        system.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="ensurepip missing")
    )
    assert system.ensure_venv(lambda *args: logs.append(args)) == ("/system/python", False)


def test_get_ollama_path_platform_candidates(monkeypatch, tmp_path) -> None:
    binary = tmp_path / "ollama"
    binary.write_text("", encoding="utf-8")
    monkeypatch.setattr(system, "SYSTEM", "linux")
    monkeypatch.setattr(system, "OLLAMA_EXE", binary)
    monkeypatch.setattr(system.os.path, "exists", lambda path: str(path) == str(binary))
    assert system.get_ollama_path() == str(binary)
    monkeypatch.setattr(system.os.path, "exists", lambda path: False)
    monkeypatch.setattr(system.shutil, "which", lambda name: "/usr/bin/ollama")
    assert system.get_ollama_path() == "/usr/bin/ollama"


def test_venv_python_linux(monkeypatch) -> None:
    monkeypatch.setattr(system, "SYSTEM", "linux")
    monkeypatch.setattr(system, "VENV_DIR", "/venv")
    assert system._venv_python() == system.os.path.join("/venv", "bin", "python")


def test_ensure_venv_logs_success_after_creation(monkeypatch) -> None:
    logs = []
    monkeypatch.setattr(system, "find_python", lambda: "/system/python")
    monkeypatch.setattr(system, "_portable_candidates", lambda: [])
    monkeypatch.setattr(system, "_is_embeddable", lambda _: False)
    monkeypatch.setattr(system, "_venv_python", lambda: "/venv/python")
    monkeypatch.setattr(system.os.path, "exists", lambda path: False)
    responses = iter([SimpleNamespace(returncode=0, stderr=""), SimpleNamespace(returncode=0, stderr="")])
    monkeypatch.setattr(system.subprocess, "run", lambda *args, **kwargs: next(responses))
    assert system.ensure_venv(lambda *args: logs.append(args)) == ("/venv/python", False)
    assert ("Setup", "OK", True) in logs


def test_get_ollama_path_macos_candidate(monkeypatch) -> None:
    monkeypatch.setattr(system, "SYSTEM", "darwin")
    monkeypatch.setattr(system.os.path, "exists", lambda path: False)
    monkeypatch.setattr(system.shutil, "which", lambda name: None)
    assert system.get_ollama_path() is None
