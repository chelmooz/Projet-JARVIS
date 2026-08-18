#!/usr/bin/env python3
"""Tests pour la gestion des accents dans le routage d'agents."""

import pytest

from services.router import AgentRouter, load_routing_config


class TestAgentRoutingAccents:
    """Tests de routage avec mots-clés accentués."""

    @pytest.fixture
    def router(self) -> AgentRouter:
        """Router avec la config réelle."""
        config = load_routing_config()
        return AgentRouter(config)

    def test_routing_with_accented_network(self, router: AgentRouter) -> None:
        """Question avec 'réseau' accentué doit router vers @network."""
        task = "Quelle technique d'attaque réseau utilise le flooding SYN ?"
        agent = router.select_agent(task)
        assert agent == "network", f"Attendu 'network', obtenu '{agent}' pour: {task}"

    def test_routing_with_accented_security(self, router: AgentRouter) -> None:
        """Question avec 'sécurité' accentué doit router vers @cyber."""
        task = "Analyse de sécurité du pare-feu"
        agent = router.select_agent(task)
        assert agent == "cyber", f"Attendu 'cyber', obtenu '{agent}' pour: {task}"

    def test_routing_without_accent_still_works(self, router: AgentRouter) -> None:
        """Mots-clés sans accent (existant) doivent encore fonctionner (non-régression)."""
        task = "reseau et securite"
        agent = router.select_agent(task)
        # "reseau" -> network, "securite" -> cyber, mais network a 1 match, cyber a 1 match
        # Le premier dans l'ordre du dict gagne (ou max avec tie-break)
        assert agent in ("network", "cyber"), f"Attendu 'network' ou 'cyber', obtenu '{agent}' pour: {task}"
