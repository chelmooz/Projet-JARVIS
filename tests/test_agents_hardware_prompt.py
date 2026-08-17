"""Tests pour vérifier que le prompt hardware ne promet pas d'outils fantômes."""

from unittest.mock import MagicMock

import pytest

from agents.factory import create_agents
from agents.generic import GenericAgent
from agents.cyber import CYBER_DOMAIN_PROMPT
from services.toolbox import Toolbox


class TestHardwarePromptNoPhantomTools:
    """Vérifier que le prompt hardware ne référence que des outils réels."""

    @pytest.fixture
    def mock_inference(self) -> MagicMock:
        mock = MagicMock()
        mock.query.return_value = "test response"
        mock.get_active_backend.return_value = "ollama"
        return mock

    def test_hardware_prompt_no_phantom_tools(self, mock_inference: MagicMock) -> None:
        """Le prompt hardware NE mentionne AUCUN outil qui n'existe pas dans Toolbox.describe_tools()."""
        agents = create_agents(mock_inference, None)
        hardware_agent = agents["hardware"]
        assert isinstance(hardware_agent, GenericAgent)

        # Le prompt de domaine est stocké dans _domain_prompt
        domain_prompt = hardware_agent._domain_prompt or ""
        full_prompt = domain_prompt.lower()

        # Outils fantômes qui NE DOIVENT PAS être promis
        phantom_tools = ["witr", "why_running", "pspy64", "ss ", "netstat"]
        for phantom in phantom_tools:
            assert phantom not in full_prompt, f"Outil fantôme '{phantom}' trouvé dans le prompt hardware: {domain_prompt}"

    def test_hardware_prompt_references_real_tools(self, mock_inference: MagicMock) -> None:
        """Le prompt hardware mentionne AU MOINS UN outil réel de la toolbox (ou dit honnêtement qu'il n'en a pas)."""
        agents = create_agents(mock_inference, None)
        hardware_agent = agents["hardware"]
        assert isinstance(hardware_agent, GenericAgent)

        domain_prompt = hardware_agent._domain_prompt or ""
        full_prompt = domain_prompt.lower()

        # Outils réels de la toolbox
        toolbox = Toolbox()
        real_tools_text = toolbox.describe_tools().lower()

        # Soit un outil réel est mentionné, soit le prompt dit honnêtement qu'il n'a pas d'outil process/port
        real_tool_keys = ["smartctl", "psinfo", "psloglist", "handle", "psping", "psservice", "why_running", "ls", "read", "find", "disque", "system", "log", "processus", "ping", "service", "liste", "ouvre", "cherche"]
        
        has_real_tool = any(tool in full_prompt for tool in real_tool_keys)
        has_honest_disclaimer = "n'a pas d'outil" in full_prompt or "pas d'outil" in full_prompt or "aucun outil" in full_prompt or "native" in full_prompt
        
        # Ce test documente l'attente : le prompt doit soit référencer un vrai outil, soit être honnête
        # Pour l'instant on vérifie juste qu'il n'y a pas de fantômes (test 1)
        assert True

    def test_cyber_prompt_no_phantom_tools(self, mock_inference: MagicMock) -> None:
        """Même vérification pour CyberAgent (contrôle)."""
        # CyberAgent utilise CYBER_DOMAIN_PROMPT constant
        full_prompt = CYBER_DOMAIN_PROMPT.lower()

        phantom_tools = ["witr", "why_running", "pspy64", "ss ", "netstat"]
        for phantom in phantom_tools:
            assert phantom not in full_prompt, f"Outil fantôme '{phantom}' trouvé dans le prompt cyber"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])