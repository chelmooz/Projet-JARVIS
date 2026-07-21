"""Tests Toolbox — auto_execute, describe_tools, injection agent."""
import os
import shutil
import tempfile

import yaml

from agents.base import BaseAgent
from services.diagnostic_ext import DiagnosticExtService
from services.file_system import FileSystemService
from services.toolbox import Toolbox

SAMPLE_CONFIG = {
    "tools": {
        "smartctl": {
            "binary": "smartctl.exe", "timeout": 5, "platforms": ["win32"],
            "args": ["-a", "{device}"],
            "sha256": "E38945652D86A4B0CDFEE8A63EE2737F2026A68D4C164A3B7C78EDC10B807507",
        },
        "psinfo": {
            "binary": "PsInfo64.exe", "timeout": 5, "platforms": ["win32"],
            "args": ["-s", "-d"],
            "sha256": "DE73B73EEB156F877DE61F4A6975D06759292ED69F31AAF06C9811F3311E03E7",
        },
    },
}


class TestToolbox:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        config_path = f"{self.tmpdir}/tools.yaml"
        with open(config_path, "w") as f:
            yaml.dump(SAMPLE_CONFIG, f)
        bin_dir = f"{self.tmpdir}/bin"
        consent_file = f"{self.tmpdir}/.consent"
        diag = DiagnosticExtService(
            config_path=config_path, bin_dir=bin_dir, consent_file=consent_file,
        )
        self.fs = FileSystemService()
        self.toolbox = Toolbox(diag, file_service=self.fs)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_disabled_by_default(self):
        # Toolbox n'a plus de mécanisme de désactivation — toujours actif
        assert "disponibles" in self.toolbox.describe_tools().lower()

    def test_describe_tools_returns_list_when_enabled(self):
        assert "disponibles" in self.toolbox.describe_tools().lower()

    def test_auto_execute_returns_empty_when_no_match(self):
        results = self.toolbox.auto_execute("rien a voir")
        assert results == {}

    def test_auto_execute_triggers_disk_keywords_returns_error_without_binaries(self):
        for kw in ["disque", "disk", "smart", "hdd", "ssd", "stockage"]:
            results = self.toolbox.auto_execute(f"analyse {kw} c:")
            assert "disk" in results  # les diagnostics tournent toujours (mono-user)
            assert not results["disk"]["success"]  # echec car binaire absent

    def test_describe_tools_show_files_when_authorized(self):
        self.fs.authorize_path(tempfile.gettempdir())
        desc = self.toolbox.describe_tools()
        assert "ls" in desc
        assert "read" in desc
        assert "find" in desc

    def test_auto_execute_ls(self):
        self.fs.authorize_path(self.tmpdir)
        results = self.toolbox.auto_execute(f"liste dossier {self.tmpdir}")
        assert "ls" in results
        assert results["ls"]["success"]

    def test_auto_execute_ls_echoue_sans_auth(self):
        results = self.toolbox.auto_execute(f"liste dossier {tempfile.gettempdir()}")
        assert "ls" in results
        assert not results["ls"]["success"]

    def test_auto_execute_read(self):
        test_file = os.path.join(self.tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("hello world")
        self.fs.authorize_path(self.tmpdir)
        results = self.toolbox.auto_execute(f"lit le fichier {test_file}")
        assert "read" in results
        assert results["read"]["success"]
        assert "hello" in results["read"]["content"]

    def test_auto_execute_find(self):
        self.fs.authorize_path(self.tmpdir)
        results = self.toolbox.auto_execute(f"cherche *.txt dans {self.tmpdir}")
        assert "find" in results
        assert results["find"]["success"]

    def test_tool_results_to_prompt_list_dir(self):
        results = {"ls": {"success": True, "entries": [
            {"name": "f.txt", "is_dir": False, "size": 100},
            {"name": "d", "is_dir": True, "size": 0},
        ]}}
        out = self.toolbox.tool_results_to_prompt(results)
        assert "f.txt" in out
        assert "d" in out

    def test_tool_results_to_prompt_read_file(self):
        results = {"read": {"success": True, "content": "lorem ipsum"}}
        out = self.toolbox.tool_results_to_prompt(results)
        assert "lorem ipsum" in out

    def test_tool_results_to_prompt_find(self):
        results = {"find": {"success": True, "matches": ["a.txt", "b.txt"]}}
        out = self.toolbox.tool_results_to_prompt(results)
        assert "a.txt" in out

    def test_injection_dans_agent_prompt_contient_outils(self):
        """Verifie que _build_messages injecte describe_tools() dans le prompt."""
        agent = _MinimalAgent()
        agent.inject_toolbox(self.toolbox)
        system, user = agent._build_messages("dev", "test task", {})
        assert "Outils disponibles" in user

    def test_injection_agent_dossiers_autorises(self):
        """Avec un dossier autorise, les outils fichiers apparaissent."""
        self.fs.authorize_path(tempfile.gettempdir())
        agent = _MinimalAgent()
        agent.inject_toolbox(self.toolbox)
        system, user = agent._build_messages("dev", "test task", {})
        assert "ls" in user
        assert "read" in user
        assert "find" in user


class _MinimalAgent(BaseAgent):
    """Sous-classe minimale concrete pour tester _build_messages."""
    def run(self, task, model, context):
        return {"response": "ok"}


def test_fallback_dir_is_project_root():
    from config.paths import ROOT
    from services.toolbox import FALLBACK_DIR
    assert FALLBACK_DIR == ROOT
