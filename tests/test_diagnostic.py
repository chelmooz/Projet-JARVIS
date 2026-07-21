"""Tests DiagnosticService — 8 checks + rapport + recommandations."""
import pytest

from services.diagnostic import DiagnosticService


def _mock_full_results():
    return {
        "host": {
            "os": "linux", "dist": "Ubuntu 22.04",
            "arch": "x86_64", "hostname": "test-pc", "kernel": "5.15.0",
        },
        "cpu": {
            "model": "Intel(R) Core(TM) i7-10700K",
            "arch": "x86_64", "apple_silicon": False,
            "cores_logical": 8, "cores_physical": 4,
            "load_percent": 25.0, "arch_bits": 64,
        },
        "ram": {
            "total_gb": 16.0, "available_gb": 8.0,
            "used_percent": 50.0, "swap_gb": 2.0,
        },
        "gpu": {"detected": True, "vendor": "nvidia", "detail": "NVIDIA GeForce RTX 4060", "vram_gb": 8.0},
        "python": {
            "version": "3.12.0", "executable": "/usr/bin/python3",
            "in_venv": True, "venv_ok": True, "missing_deps": [],
        },
        "binaries": [
            {"name": "ollama", "path": "/usr/bin/ollama",
             "exists": True, "file_info": "ELF 64-bit LSB executable"},
        ],
        "network": {
            "internet": True,
            "ports": {"11434": "in_use", "11436": "free", "8000": "free", "3000": "free"},
        },
        "disk": {
            "project_dir": "J:\\Projet JARVIS", "mount_point": "J:\\",
            "total_gb": 100.0, "free_gb": 50.0, "used_percent": 50.0,
        },
    }


class TestDiagnostic:

    def setup_method(self):
        self.d = DiagnosticService()

    @staticmethod
    def _patch_all_checks(monkeypatch):
        m = _mock_full_results()
        monkeypatch.setattr("services.diagnostics.service.check_os", lambda: m["host"])
        monkeypatch.setattr("services.diagnostics.service.check_cpu", lambda: m["cpu"])
        monkeypatch.setattr("services.diagnostics.service.check_ram", lambda: m["ram"])
        monkeypatch.setattr("services.diagnostics.service.check_gpu", lambda: m["gpu"])
        monkeypatch.setattr("services.diagnostics.service.check_python", lambda: m["python"])
        monkeypatch.setattr("services.diagnostics.service.check_binaries", lambda: m["binaries"])
        monkeypatch.setattr("services.diagnostics.service.check_network", lambda: m["network"])
        monkeypatch.setattr("services.diagnostics.service.check_disk", lambda: m["disk"])

    _OS_KEYS = ["os", "arch", "hostname"]

    @pytest.mark.parametrize("key", _OS_KEYS)
    def test_check_os_returns_key(self, monkeypatch, key):
        monkeypatch.setattr("services.diagnostics.service.check_os",
                            lambda: {"os": "linux", "arch": "x86_64", "hostname": "test"})
        assert key in self.d.check_os()

    def test_check_cpu_returns_model(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_cpu",
                            lambda: {"model": "Intel", "arch": "x86_64", "cores_logical": 8,
                                     "cores_physical": 4, "load_percent": 25.0,
                                     "apple_silicon": False, "arch_bits": 64})
        assert "model" in self.d.check_cpu()

    def test_check_cpu_cores_positive(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_cpu",
                            lambda: {"model": "Intel", "arch": "x86_64", "cores_logical": 8,
                                     "cores_physical": 4, "load_percent": 25.0,
                                     "apple_silicon": False, "arch_bits": 64})
        assert self.d.check_cpu()["cores_logical"] > 0

    def test_check_cpu_load_range(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_cpu",
                            lambda: {"model": "Intel", "arch": "x86_64", "cores_logical": 8,
                                     "cores_physical": 4, "load_percent": 50.0,
                                     "apple_silicon": False, "arch_bits": 64})
        r = self.d.check_cpu()
        assert 0 <= r["load_percent"] <= 100

    def test_check_ram_total_positive(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_ram",
                            lambda: {"total_gb": 16.0, "available_gb": 8.0,
                                     "used_percent": 50.0, "swap_gb": 2.0})
        assert self.d.check_ram()["total_gb"] > 0

    def test_check_ram_available_positive(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_ram",
                            lambda: {"total_gb": 16.0, "available_gb": 8.0,
                                     "used_percent": 50.0, "swap_gb": 2.0})
        assert self.d.check_ram()["available_gb"] > 0

    def test_check_ram_used_percent_range(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_ram",
                            lambda: {"total_gb": 16.0, "available_gb": 8.0,
                                     "used_percent": 50.0, "swap_gb": 2.0})
        r = self.d.check_ram()
        assert 0 <= r["used_percent"] <= 100

    _GPU_KEYS = ["detected", "vendor", "detail", "vram_gb"]

    @pytest.mark.parametrize("key", _GPU_KEYS)
    def test_check_gpu_returns_key(self, monkeypatch, key):
        monkeypatch.setattr("services.diagnostics.service.check_gpu",
                            lambda: {"detected": True, "vendor": "nvidia",
                                     "detail": "NVIDIA GeForce RTX 4060",
                                     "vram_gb": 8.0})
        assert key in self.d.check_gpu()

    def test_check_gpu_vram_float(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_gpu",
                            lambda: {"detected": True, "vendor": "nvidia",
                                     "detail": "NVIDIA GeForce RTX 4060",
                                     "vram_gb": 8.0})
        assert isinstance(self.d.check_gpu()["vram_gb"], (int, float))

    def test_check_gpu_vram_non_negative(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_gpu",
                            lambda: {"detected": True, "vendor": "nvidia",
                                     "detail": "NVIDIA GeForce RTX 4060",
                                     "vram_gb": 8.0})
        assert self.d.check_gpu()["vram_gb"] >= 0

    _PYTHON_KEYS = ["version", "missing_deps"]

    @pytest.mark.parametrize("key", _PYTHON_KEYS)
    def test_check_python_returns_key(self, monkeypatch, key):
        monkeypatch.setattr("services.diagnostics.service.check_python",
                            lambda: {"version": "3.12.0", "missing_deps": []})
        assert key in self.d.check_python()

    def test_check_python_missing_deps_is_list(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_python",
                            lambda: {"version": "3.12.0", "missing_deps": ["numpy"]})
        assert isinstance(self.d.check_python()["missing_deps"], list)

    def test_check_binaries_returns_list(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_binaries", lambda: [])
        assert isinstance(self.d.check_binaries(), list)

    def test_check_binaries_contains_ollama(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_binaries",
                            lambda: [{"name": "ollama", "path": "/usr/bin/ollama",
                                      "exists": True, "file_info": "ELF 64-bit"}])
        names = {b["name"] for b in self.d.check_binaries()}
        assert "ollama" in names

    _NETWORK_KEYS = ["internet", "ports"]

    @pytest.mark.parametrize("key", _NETWORK_KEYS)
    def test_check_network_returns_key(self, monkeypatch, key):
        monkeypatch.setattr("services.diagnostics.service.check_network",
                            lambda: {"internet": True, "ports": {"11434": "in_use"}})
        assert key in self.d.check_network()

    def test_check_network_ports_is_dict(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_network",
                            lambda: {"internet": True, "ports": {"11434": "in_use"}})
        assert isinstance(self.d.check_network()["ports"], dict)

    def test_check_disk_returns_project_dir(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_disk",
                            lambda: {"project_dir": "/test", "mount_point": "/",
                                     "total_gb": 100.0, "free_gb": 50.0,
                                     "used_percent": 50.0})
        assert "project_dir" in self.d.check_disk()

    def test_check_disk_total_positive(self, monkeypatch):
        monkeypatch.setattr("services.diagnostics.service.check_disk",
                            lambda: {"project_dir": "/test", "mount_point": "/",
                                     "total_gb": 100.0, "free_gb": 50.0,
                                     "used_percent": 50.0})
        assert self.d.check_disk()["total_gb"] > 0

    _RUN_FULL_SECTIONS = [
        "host", "cpu", "ram", "gpu", "python", "binaries",
        "network", "disk", "recommendations", "verdict",
    ]

    @pytest.mark.parametrize("section", _RUN_FULL_SECTIONS)
    def test_run_full_returns_section(self, monkeypatch, section):
        self._patch_all_checks(monkeypatch)
        assert section in self.d.run_full()

    def test_recommendations_is_list(self, monkeypatch):
        self._patch_all_checks(monkeypatch)
        assert isinstance(self.d.run_full()["recommendations"], list)

    def test_recommendations_nonempty(self, monkeypatch):
        self._patch_all_checks(monkeypatch)
        assert len(self.d.run_full()["recommendations"]) > 0

    def test_verdict_is_string(self, monkeypatch):
        self._patch_all_checks(monkeypatch)
        assert isinstance(self.d.run_full()["verdict"], str)

    def test_verdict_expected_value(self, monkeypatch):
        self._patch_all_checks(monkeypatch)
        v = self.d.run_full()["verdict"]
        assert v in ("OK",) or v.startswith("WARNING") or v.startswith("FAIL")
