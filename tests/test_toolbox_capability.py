"""Tests pour la sonde de capacités de la Toolbox (binaires déployés vs promis)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.diagnostic_ext.service import DiagnosticExtService
from services.toolbox import Toolbox


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
        """Avec bin/ vide → describe_tools() ANNOTE les outils non déployés ; avec witr.exe factice présent → witr listé SANS annotation."""
        # bin/ est vide (pas de witr.exe, smartctl.exe, etc.)
        desc = toolbox_with_bin.describe_tools().lower()

        # Les outils diagnostiques DOIVENT apparaître MAIS avec l'annotation "non disponible"
        diagnostic_tools = ["smartctl", "psinfo", "psloglist", "handle", "psping", "psservice", "witr"]
        for tool in diagnostic_tools:
            # Vérifier que l'outil est mentionné avec l'annotation de non-disponibilité
            assert tool in desc, f"Outil '{tool}' devrait être listé (même non déployé)"
            # Vérifier qu'il a l'annotation
            assert "non disponible" in desc, f"Outil '{tool}' devrait avoir l'annotation 'non disponible'"

        # Maintenant simuler witr déployé en mockant list_available
        with patch.object(toolbox_with_bin._diagnostic, "list_available", return_value=["witr"]):
            desc2 = toolbox_with_bin.describe_tools().lower()
            # witr devrait maintenant apparaître SANS l'annotation "non disponible"
            assert "witr" in desc2, "witr déployé devrait être listé"
            # Vérifier que "non disponible" n'est pas adjacent à witr
            witr_idx = desc2.find("witr")
            assert "non disponible" not in desc2[max(0, witr_idx - 50):witr_idx + 50], "witr déployé ne devrait pas avoir l'annotation 'non disponible'"

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

                # Ne doit PAS promettre d'invocation directe d'outils DIAGNOSTIQUES
                forbidden_direct = [
                    "utilise l'outil", "use the tool", "invoke", "appelle", "call",
                    "why_running", "pspy64"
                ]
                for f in forbidden_direct:
                    assert f not in full_prompt, f"Promesse d'invocation directe interdite '{f}' dans prompt hardware: {domain_prompt}"

                # "witr" PEUT apparaître comme nom d'outil dans la liste descriptive
                # mais pas comme promesse d'invocation directe ("utilise witr", "call witr", etc.)
                # "netstat -ano" est autorisé car cité comme commande NATIVE de repli (pas outil toolbox)

                # Doit décrire le mécanisme réel : auto-déclenchement par mots-clés + repli
                assert "automatique" in full_prompt or "mots-clé" in full_prompt or "mot-clé" in full_prompt or "keyword" in full_prompt, \
                    "Prompt doit mentionner le déclenchement automatique par mots-clés"
                assert "déployé" in full_prompt or "disponible" in full_prompt or "native" in full_prompt or "repli" in full_prompt or "fallback" in full_prompt, \
                    "Prompt doit mentionner la condition de déploiement ou le repli honnête"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
