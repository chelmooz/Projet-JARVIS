from __future__ import annotations

import subprocess
from types import SimpleNamespace

import services.diagnostic_ext.executor as executor_module
from services.diagnostic_ext.executor import CommandExecutor


class Formatter:
    def format(self, tool_name, proc):
        return {"success": proc.returncode == 0, "tool": tool_name, "stdout": proc.stdout}


def service(config=None):
    return CommandExecutor(config or {"tools": {}}, "bin", None, set())


def test_run_unknown_missing_binary_and_sha_failure(monkeypatch) -> None:
    executor = service()
    assert executor.run("missing")["success"] is False
    config = {"tools": {"tool": {"args": []}}}
    executor = service(config)
    monkeypatch.setattr(executor_module, "resolve_binary", lambda *args: None)
    assert executor.run("tool")["error"].startswith("Binaire")
    monkeypatch.setattr(executor_module, "resolve_binary", lambda *args: "/bin/tool")
    monkeypatch.setattr(executor_module, "resolve_expected_sha256", lambda *args: "sha")
    monkeypatch.setattr(executor, "_verify", lambda *args: False)
    assert executor.run("tool")["error"] == "Échec vérification SHA256"


def test_run_builds_args_formatter_and_executes(monkeypatch) -> None:
    config = {
        "tools": {
            "tool": {
                "linux_args": ["--name", "{name}"],
                "allowed_params": ["name"],
                "output_format": "json",
                "timeout": 4,
            }
        }
    }
    executor = service(config)
    monkeypatch.setattr(executor_module.sys, "platform", "linux")
    monkeypatch.setattr(executor_module, "resolve_binary", lambda *args: "/bin/tool")
    monkeypatch.setattr(executor_module, "resolve_expected_sha256", lambda *args: "")
    monkeypatch.setattr(executor_module, "get_formatter", lambda *args: Formatter())
    monkeypatch.setattr(executor, "_execute", lambda *args: {"success": True, "args": args[2], "timeout": args[3]})
    result = executor.run("tool", extra_kwargs={"name": "demo"})
    assert result == {"success": True, "args": ["--name", "demo"], "timeout": 4}


def test_build_args_platform_port_and_no_kwargs(monkeypatch) -> None:
    cfg = {"args": ["generic"], "linux_args": ["linux"], "port_args": ["--port", "{port}"], "allowed_params": ["port"]}
    executor = service()
    monkeypatch.setattr(executor_module.sys, "platform", "linux")
    assert executor.build_args(cfg, None, None) == ["linux"]
    assert executor.build_args(cfg, None, {"port": 8080}) == ["--port", "8080"]
    monkeypatch.setattr(executor_module.sys, "platform", "win32")
    assert executor.build_args(cfg, None, None) == ["generic"]


def test_build_args_whitelist_invalid_and_unknown_placeholders() -> None:
    cfg = {"allowed_params": ["good", "bad"]}
    executor = service()
    args = executor.build_args(cfg, ["{good}", "{unknown}", "{bad}"], {"good": "ok", "bad": "bad/value", "extra": "x"})
    assert args == ["ok", "{unknown}", "{bad}"]


def test_format_result_and_verify(monkeypatch) -> None:
    monkeypatch.setattr(executor_module, "get_formatter", lambda *args: Formatter())
    proc = SimpleNamespace(returncode=0, stdout="out")
    assert CommandExecutor.format_result("tool", proc) == {"success": True, "tool": "tool", "stdout": "out"}
    monkeypatch.setattr(executor_module, "verify_sha256", lambda *args: True)
    executor = service()
    assert executor._verify("tool", "/bin/tool", "sha") is True


def test_execute_success_timeout_missing_and_generic(monkeypatch) -> None:
    executor = service()
    formatter = Formatter()
    monkeypatch.setattr(
        executor_module.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ok")
    )
    assert executor._execute("tool", "/bin/tool", [], 1, formatter)["success"] is True

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="tool", timeout=1)

    monkeypatch.setattr(executor_module.subprocess, "run", timeout)
    assert "Timeout" in executor._execute("tool", "/bin/tool", [], 1, formatter)["error"]
    monkeypatch.setattr(
        executor_module.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError())
    )
    assert "Binaire" in executor._execute("tool", "/bin/tool", [], 1, formatter)["error"]
    monkeypatch.setattr(
        executor_module.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert executor._execute("tool", "/bin/tool", [], 1, formatter)["error"] == "boom"
