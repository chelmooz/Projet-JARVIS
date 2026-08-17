"""Tests pour vérifier que le prompt hardware est honnête sur ses capacités."""

from unittest.mock import MagicMock

import pytest

from agents.cyber import CYBER_DOMAIN_PROMPT
from agents.factory import create_agents
from agents.generic import GenericAgent


class TestHardwarePromptHonestCapabilities:
    """Vérifier que le prompt hardware décrit honnêtement ses capacités."""

    @pytest.fixture
    def mock_inference(self) -> MagicMock:
        mock = MagicMock()
        mock.query.return_value = "test response"
        mock.get_active_backend.return_value = "ollama"
        return mock

    def test_hardware_prompt_no_direct_invocation_promise(self, mock_inference: MagicMock) -> None:
        """Le prompt hardware NE promet PAS d'invocation directe d'outils ("utilise l'outil X")."""
        agents = create_agents(mock_inference, None)
        hardware_agent = agents["hardware"]
        assert isinstance(hardware_agent, GenericAgent)

        domain_prompt = hardware_agent._domain_prompt or ""
        full_prompt = domain_prompt.lower()

        # NE DOIT PAS promettre d'invocation directe
        forbidden_direct = [
            "utilise l'outil", "use the tool", "invoke", "appelle", "call",
            "why_running", "pspy64"
        ]
        for f in forbidden_direct:
            assert f not in full_prompt, f"Promesse d'invocation directe interdite '{f}' dans le prompt hardware: {domain_prompt}"

        # PEUT mentionner les noms d'outils réels (witr, smartctl, etc.) dans la liste descriptive
        # mais seulement comme outils qui se déclenchent automatiquement

    def test_hardware_prompt_describes_real_mechanism(self, mock_inference: MagicMock) -> None:
        """Le prompt hardware décrit le mécanisme réel : auto-déclenchement par mots-clés + condition déploiement + repli natif."""
        agents = create_agents(mock_inference, None)
        hardware_agent = agents["hardware"]

        domain_prompt = hardware_agent._domain_prompt or ""
        full_prompt = domain_prompt.lower()

        # Doit mentionner le déclenchement automatique par mots-clés
        assert "automatique" in full_prompt or "mots-clé" in full_prompt or "mot-clé" in full_prompt or "keyword" in full_prompt, \
            "Prompt doit mentionner le déclenchement automatique par mots-clés"

        # Doit mentionner la condition de déploiement
        assert "déployé" in full_prompt or "disponible" in full_prompt, \
            "Prompt doit mentionner la condition de déploiement des binaires"

        # Doit mentionner le repli honnête (commandes natives)
        assert "native" in full_prompt or "repli" in full_prompt or "fallback" in full_prompt or "honnêtement" in full_prompt, \
            "Prompt doit mentionner le repli honnête (commandes natives)"

    def test_hardware_prompt_references_real_tool_names(self, mock_inference: MagicMock) -> None:
        """Le prompt hardware PEUT lister les noms d'outils réels (witr, smartctl, etc.) comme outils disponibles."""
        agents = create_agents(mock_inference, None)
        hardware_agent = agents["hardware"]

        domain_prompt = hardware_agent._domain_prompt or ""
        full_prompt = domain_prompt.lower()

        # Les noms d'outils réels de la toolbox peuvent apparaître
        real_tool_names = ["smartctl", "psinfo", "psloglist", "handle", "psping", "psservice", "witr"]
        # Au moins un nom d'outil réel devrait être mentionné
        assert any(tool in full_prompt for tool in real_tool_names), \
            f"Prompt devrait mentionner au moins un nom d'outil réel parmi {real_tool_names}"

    def test_cyber_prompt_no_phantom_tools(self, mock_inference: MagicMock) -> None:
        """Même vérification pour CyberAgent (contrôle) : pas de promesse d'invocation directe."""
        full_prompt = CYBER_DOMAIN_PROMPT.lower()

        # CyberAgent ne doit pas promettre d'invocation directe d'outils diagnostiques
        forbidden = ["utilise l'outil", "use the tool", "invoke", "appelle", "call", "why_running", "pspy64"]
        for f in forbidden:
            assert f not in full_prompt, f"Promesse d'invocation directe interdite '{f}' dans le prompt cyber"
