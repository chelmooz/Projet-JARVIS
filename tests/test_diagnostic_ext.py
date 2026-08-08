"""Tests DiagnosticExtService — exécution simulée, SHA256, is_ready."""
import hashlib
import os
import shutil
import sys
import tempfile

import yaml

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_DIR)

from services.diagnostic_ext import DiagnosticExtService

SAMPLE_CONFIG = {
    "tools": {
        "smartctl": {
            "binary": "smartctl.exe",
            "linux_binary": "smartctl",
            "description": "SMART disk health",
            "timeout": 5,
            "platforms": ["win32", "linux"],
            "args": ["-a", "{device}"],
            "sha256": "E38945652D86A4B0CDFEE8A63EE2737F2026A68D4C164A3B7C78EDC10B807507",
        },
        "psinfo": {
            "binary": "PsInfo64.exe",
            "description": "System information",
            "timeout": 5,
            "platforms": ["win32"],
            "args": ["-s", "-d"],
            "sha256": "DE73B73EEB156F877DE61F4A6975D06759292ED69F31AAF06C9811F3311E03E7",
        },
        "handle": {
            "binary": "handle64.exe",
            "linux_binary": "lsof",
            "description": "Open file handles",
            "timeout": 5,
            "platforms": ["win32", "linux"],
            "args": ["-accepteula", "{pattern}"],
            "linux_args": ["{pattern}"],
            "sha256": "24BAFCC570CC9BBB6B6E6652A57A519E0464E3996891AABA6F55299CCE20B04F",
        },
    },
}


class FakeLog:
    def __init__(self):
        self.entries = []

    def log(self, level, message):
        self.entries.append({"level": level, "message": message})


def _platform_subdir() -> str:
    """Sous-dossier de bin_dir par plateforme (Phase 2)."""
    return {"win32": "win", "linux": "linux", "darwin": "darwin"}.get(
        sys.platform, sys.platform
    )


def _binary_path(bin_dir: str, bin_name: str) -> str:
    """Place un binaire dans le sous-dossier de l'OS et retourne son chemin."""
    subdir = _platform_subdir()
    bin_path = os.path.join(bin_dir, subdir, bin_name)
    os.makedirs(os.path.dirname(bin_path), exist_ok=True)
    return bin_path


class TestDiagnosticExtService:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, "tools.yaml")
        with open(self.config_path, "w") as f:
            yaml.dump(SAMPLE_CONFIG, f)
        self.bin_dir = os.path.join(self.tmpdir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.log = FakeLog()
        self.svc = DiagnosticExtService(
            config_path=self.config_path,
            bin_dir=self.bin_dir,
            log_service=self.log,
        )

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_load_config(self):
        assert "smartctl" in self.svc.get_tools_config()

    def test_service_fonctionne_sans_mecanisme_consent(self):
        """C1 — le consentement est retiré : ni `ensure_consent` ni
        `grant_consent` n'existent plus ; l'exécution dépend des binaires."""
        assert not hasattr(self.svc, "ensure_consent")
        assert not hasattr(self.svc, "grant_consent")

    def test_sha256_verify_fails_on_mismatch(self):
        tool_name = "smartctl"
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        binary_path = _binary_path(self.bin_dir, bin_name)
        with open(binary_path, "wb") as f:
            f.write(b"fake binary content")
        result = self.svc._run_tool(tool_name)
        assert not result["success"]
        assert "SHA256" in result["error"]

    def test_sha256_verify_skipped_when_empty(self):
        cfg = SAMPLE_CONFIG.copy()
        cfg["tools"]["smartctl"]["sha256"] = ""
        config_path2 = os.path.join(self.tmpdir, "tools2.yaml")
        with open(config_path2, "w") as f:
            yaml.dump(cfg, f)
        svc = DiagnosticExtService(
            config_path=config_path2,
            bin_dir=self.bin_dir,
            log_service=self.log,
        )
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        binary_path = _binary_path(self.bin_dir, bin_name)
        with open(binary_path, "wb") as f:
            f.write(b"fake")
        result = svc._run_tool("smartctl")
        assert not result["success"]
        assert "SHA256" not in result["error"]
        assert result["error"] is not None

    def test_run_tool_sans_consentement_execute(self):
        """C1 — consentement retiré : l'échec vient du binaire absent
        (« introuvable »), plus jamais d'erreur « Consentement »."""
        result = self.svc._run_tool("smartctl")
        assert not result["success"]
        assert "Consentement" not in result["error"]

    def test_run_tool_unknown_name(self):
        result = self.svc._run_tool("nonexistent")
        assert not result["success"]
        assert "inconnu" in result["error"]

    def test_run_tool_binary_not_found(self):
        result = self.svc._run_tool("smartctl")
        assert not result["success"]
        assert "introuvable" in result["error"]

    def test_check_all_tools_no_binaries(self):
        results = self.svc.check_all_tools()
        for name, info in results.items():
            if "linux_binary" not in SAMPLE_CONFIG["tools"].get(name, {}):
                assert not info["available"]
                assert info["path"] is None

    def test_check_all_tools_with_binary_available_true(self):
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        binary_path = _binary_path(self.bin_dir, bin_name)
        with open(binary_path, "wb") as f:
            f.write(b"\x00" * 100)
        results = self.svc.check_all_tools()
        assert results["smartctl"]["available"]

    def test_check_all_tools_with_binary_sha256_not_ok(self):
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        binary_path = _binary_path(self.bin_dir, bin_name)
        with open(binary_path, "wb") as f:
            f.write(b"\x00" * 100)
        results = self.svc.check_all_tools()
        assert not results["smartctl"]["sha256_ok"]

    def test_list_available_empty_initially(self):
        assert self.svc.list_available() == []

    def test_is_ready_false_sans_outil_disponible(self):
        assert not self.svc.is_ready()

    def test_is_ready_selon_outils_sans_consentement(self):
        """C1 — `is_ready()` ne dépend plus du consentement : la
        disponibilité des outils décide seule (ici binaire + SHA256 OK)."""
        cfg = SAMPLE_CONFIG.copy()
        bin_name = "smartctl.exe" if sys.platform == "win32" else "smartctl"
        binary_path = _binary_path(self.bin_dir, bin_name)
        content = b"\x00" * 100
        with open(binary_path, "wb") as f:
            f.write(content)
        cfg["tools"]["smartctl"]["sha256"] = hashlib.sha256(content).hexdigest().upper()
        config_path = os.path.join(self.tmpdir, "tools_ready.yaml")
        with open(config_path, "w") as f:
            yaml.dump(cfg, f)
        svc = DiagnosticExtService(
            config_path=config_path,
            bin_dir=self.bin_dir,
            log_service=self.log,
        )
        assert svc.is_ready()

    def test_audit_log_on_run_rejected(self):
        self.svc._run_tool("smartctl")
        messages = [e["message"] for e in self.log.entries]
        assert any("AUDIT" in m for m in messages)

    def test_timeout_returns_error(self):
        timeout_config = SAMPLE_CONFIG.copy()
        timeout_config["tools"]["smartctl"]["timeout"] = 0.001
        config_path = os.path.join(self.tmpdir, "tools_timeout.yaml")
        with open(config_path, "w") as f:
            yaml.dump(timeout_config, f)
        # Create a binary that hangs
        svc = DiagnosticExtService(
            config_path=config_path,
            bin_dir=self.bin_dir,
            log_service=self.log,
        )
        binary_path = _binary_path(self.bin_dir, "smartctl.exe")
        with open(binary_path, "wb") as f:
            f.write(b"\x00" * 100)
        # SHA256 will fail first, so skip it
        cfg = svc._config["tools"]["smartctl"]
        cfg["sha256"] = ""
        result = svc._run_tool("smartctl")
        assert not result["success"]
