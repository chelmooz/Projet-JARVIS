from __future__ import annotations

import services.diagnostic_ext.service as service_module
from services.diagnostic_ext.service import DiagnosticExtService


def make_service(monkeypatch):
    config = {"tools": {"tool": {"platforms": ["linux"]}, "witr": {"platforms": ["linux"]}}}
    monkeypatch.setattr(service_module, "load_config", lambda path: config)
    return DiagnosticExtService("config.yaml", "bin")


def test_get_tools_config_and_run_wrappers(monkeypatch) -> None:
    service = make_service(monkeypatch)
    calls = []
    monkeypatch.setattr(service, "_run_tool", lambda *args, **kwargs: calls.append((args, kwargs)) or {"ok": True})
    assert service.get_tools_config()["tool"]
    assert service.run_smartctl() == {"ok": True}
    assert service.run_smartctl("/dev/nvme0") == {"ok": True}
    service.run_psinfo()
    service.run_psloglist("Application")
    service.run_handle("python")
    service.run_psping("localhost", "2")
    service.run_psservice("sshd")
    service.run_witr("8080")
    service.run_witr("python")
    assert len(calls) == 9
    assert calls[-2][1]["extra_kwargs"] == {"port": "8080"}
    assert calls[-1][1]["extra_kwargs"] == {"target": "python"}


def test_run_tool_delegates_to_executor(monkeypatch) -> None:
    service = make_service(monkeypatch)

    class Executor:
        def __init__(self, config, bin_dir, log, verified):
            self.args = (config, bin_dir, log, verified)

        def run(self, tool_name, args, extra_kwargs):
            return {"tool": tool_name, "args": args, "extra": extra_kwargs}

    monkeypatch.setattr(service_module, "CommandExecutor", Executor)
    assert service._run_tool("tool", ["--json"], {"x": 1}) == {"tool": "tool", "args": ["--json"], "extra": {"x": 1}}


def test_check_tool_available_hash_ok_and_list_ready(monkeypatch) -> None:
    service = make_service(monkeypatch)
    monkeypatch.setattr(service_module, "resolve_binary", lambda config, name, bin_dir: "/bin/tool")
    monkeypatch.setattr(service_module, "resolve_expected_sha256", lambda *args: "sha")
    monkeypatch.setattr(service_module, "verify_sha256", lambda *args: True)
    info = service._check_tool("tool")
    assert info == {"available": True, "path": "/bin/tool", "sha256_ok": True, "platforms": ["linux"]}
    assert service.list_available() == ["tool", "witr"]
    assert service.is_ready() is True


def test_check_tool_missing_path_or_hash_and_not_ready(monkeypatch) -> None:
    service = make_service(monkeypatch)
    monkeypatch.setattr(service_module, "resolve_binary", lambda *args: None)
    monkeypatch.setattr(service_module, "resolve_expected_sha256", lambda *args: "sha")
    info = service._check_tool("tool")
    assert info["available"] is False
    assert info["sha256_ok"] is False
    monkeypatch.setattr(service, "check_all_tools", lambda: {"tool": {"available": True, "sha256_ok": False}})
    assert service.list_available() == []
    assert service.is_ready() is False


def test_check_tool_without_expected_hash_skips_verification(monkeypatch) -> None:
    service = make_service(monkeypatch)
    monkeypatch.setattr(service_module, "resolve_binary", lambda *args: "/bin/tool")
    monkeypatch.setattr(service_module, "resolve_expected_sha256", lambda *args: "")
    called = []
    monkeypatch.setattr(service_module, "verify_sha256", lambda *args: called.append(args) or True)
    assert service._check_tool("tool")["sha256_ok"] is False
    assert called == []
