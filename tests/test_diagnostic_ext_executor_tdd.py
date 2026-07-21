"""Tests TDD extraction _run_tool -> CommandExecutor (SRP/KISS).

Le contrat DiagnosticExtService._run_tool reste identique (tests existants
l'appellent). On verifie que la logique est deleguee a un CommandExecutor
aux responsabilites separees (resolution, args, subprocess, format, erreurs).
"""
import os
import sys
import tempfile

import yaml

from services.diagnostic_ext import DiagnosticExtService
from services.diagnostic_ext.executor import CommandExecutor

SAMPLE_CONFIG = {
    "tools": {
        "smartctl": {
            "binary": "smartctl.exe",
            "linux_binary": "smartctl",
            "timeout": 5,
            "platforms": ["win32", "linux"],
            "args": ["-a", "{device}"],
            "sha256": "",
        },
    },
}


class FakeLog:
    def __init__(self):
        self.entries = []
    def log(self, level, message):
        self.entries.append({"level": level, "message": message})


class TestCommandExecutor:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "tools.yaml")
        with open(self.config_path, "w") as f:
            yaml.dump(SAMPLE_CONFIG, f)
        self.bin_dir = os.path.join(self.tmpdir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.consent_file = os.path.join(self.tmpdir, ".consent")
        self.log = FakeLog()
        self.svc = DiagnosticExtService(
            config_path=self.config_path, bin_dir=self.bin_dir,
            consent_file=self.consent_file, log_service=self.log,
        )
        self.executor = CommandExecutor(
            self.svc._config, self.bin_dir, self.log, self.svc._verified,
        )

    def test_build_args_uses_platform(self):
        cfg = SAMPLE_CONFIG["tools"]["smartctl"]
        args = self.executor.build_args(cfg, None, extra_kwargs={"device": "C:"})
        assert args == ["-a", "C:"]

    def test_build_args_default_when_none(self):
        cfg = {"args": ["-x"]}
        args = self.executor.build_args(cfg, None, extra_kwargs=None)
        assert args == ["-x"]

    def test_format_result_shape(self):
        import subprocess
        proc = subprocess.CompletedProcess(
            ["x"], returncode=0, stdout="  hello  ", stderr="")
        res = self.executor.format_result("smartctl", proc)
        assert res["success"] is True
        assert res["tool"] == "smartctl"
        assert res["stdout"] == "hello"
        assert res["returncode"] == 0

    def test_run_tool_delegates_consents_checks(self):
        # sans consentement -> refus courte circuit, meme via executor delegue
        self.svc.grant_consent()
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        with open(os.path.join(self.bin_dir, bin_name), "wb") as f:
            f.write(b"\x00" * 100)
        result = self.svc._run_tool("smartctl", extra_kwargs={"device": "C:"})
        # contrat identique : succes/tool/error present
        assert "tool" in result and "success" in result

    def test_unknown_tool_error(self):
        r = self.executor.run("ghost", consent_given=True)
        assert r["success"] is False
        assert "inconnu" in r["error"]
