"""Tests pour la sonde de capacités de la Toolbox (binaires déployés vs promis)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.toolbox import Toolbox
from services.diagnostic_ext.service import DiagnosticExtService


class TestToolboxCapability:
    """Vérifier que la Toolbox expose honnêtement ses capacités réelles."""

    @pytest.fixture
    def temp_bin_dir(self) -> Path:
        """Crée un répertoire bin temporaire vide."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def toolbox_with_bin(self, temp_bin_dir: Path) -> Toolbox:
        """Toolbox avec chemin bin injecté."""
        # On doit patcher le chemin BIN_DIR utilisé par DiagnosticExtService
        with patch("services.diagnostic_ext.config.BIN_DIR", str(temp_bin_dir)):
            with patch("services.diagnostic_ext.config.CONFIG_PATH", str(Path("config") / "diagnostic_tools.yaml")):
                diagnostic = DiagnosticExtService()
                return Toolbox(diagnostic_service=diagnostic)

    def test_describe_tools_only_deployed_binaries(self, toolbox_with_bin: Toolbox, temp_bin_dir: Path) -> None:
        """Avec bin/ vide → describe_tools() ne promet aucun outil diagnostique externe."""
        # bin/ est vide (pas de witr.exe, smartctl.exe, etc.)
        desc = toolbox_with_bin.describe_tools().lower()

        # Les outils diagnostiques ne doivent PAS apparaître dans la description
        diagnostic_tools = ["smartctl", "psinfo", "psloglist", "handle", "psping", "psservice", "witr", "why_running"]
        for tool in diagnostic_tools:
            assert tool not in desc, f"Outil non déployé '{tool}' listé dans describe_tools(): {desc}"

        # Maintenant ajouter witr.exe factice
        (temp_bin_dir / "witr.exe").write_bytes(b"fake")
        # Re-créer la toolbox pour recharger
        with patch("services.diagnostic_ext.config.BIN_DIR", str(temp_bin_dir)):
            with patch("services.diagnostic_ext.config.CONFIG_PATH", str(Path("config") / "diagnostic_tools.yaml")):
                diagnostic = DiagnosticExtService()
                toolbox2 = Toolbox(diagnostic_service=diagnostic)
                desc2 = toolbox2.describe_tools().lower()
                # witr devrait maintenant apparaître (ou être listé avec disponibilité)
                # Au minimum, la description ne doit pas être vide pour les outils déployés
                assert "witr" in desc2 or "why_running" in desc2, "witr déployé devrait être listé"

    def test_capability_probe_reports_missing(self, toolbox_with_bin: Toolbox) -> None:
        """capability_report() retourne {outil: bool} pour chaque entrée de diagnostic_tools.yaml."""
        report = toolbox_with_bin.capability_report()

        # Doit contenir au moins les 7 outils diagnostiques déclarés dans diagnostic_tools.yaml
        expected_tools = ["smartctl", "psinfo", "psloglist", "handle", "psping", "psservice", "witr"]
        for tool in expected_tools:
            assert tool in report, f"Outil '{tool}' manquant dans capability_report()"
            assert isinstance(report[tool], bool), f"capability_report()['{tool}'] doit être bool"

        # Avec bin/ vide, tous doivent être False
        for tool in expected_tools:
            assert report[tool] is False, f"Outil '{tool}' devrait être False (bin vide)"

    def test_hardware_prompt_no_undeployed_promise(self, temp_bin_dir: Path) -> None:
        """Le domain_prompt hardware ne promet aucun outil « à la demande » non déployé."""
        from agents.factory import create_agents

        mock_inference = MagicMock()
        mock_inference.query.return_value = "test"
        mock_inference.get_active_backend.return_value = "ollama"

        with patch("services.diagnostic_ext.config.BIN_DIR", str(temp_bin_dir)):
            with patch("services.diagnostic_ext.config.CONFIG_PATH", str(Path("config") / "diagnostic_tools.yaml")):
                agents = create_agents(mock_inference, None)
                hardware_agent = agents["hardware"]

                domain_prompt = hardware_agent._domain_prompt or ""
                full_prompt = domain_prompt.lower()

                # Ne doit PAS promettre d'invocation directe d'outils
                forbidden = [
                    "utilise l'outil", "use the tool", "invoke", "appelle", "call",
                    "witr", "why_running", "pspy64", "netstat -ano"
                ]
                for f in forbidden:
                    assert f not in full_prompt, f"Promesse interdite '{f}' dans prompt hardware: {domain_prompt}"

                # Doit décrire le mécanisme réel : auto-déclenchement par mots-clés + repli
                assert "automatique" in full_prompt or "mots-clé" in full_prompt or "mot-clé" in full_prompt or "keyword" in full_prompt, \
                    "Prompt doit mentionner le déclenchement automatique par mots-clés"
                assert "déployé" in full_prompt or "disponible" in full_prompt or "native" in full_prompt or "repli" in full_prompt or "fallback" in full_prompt, \
                    "Prompt doit mentionner la condition de déploiement ou le repli honnête"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])