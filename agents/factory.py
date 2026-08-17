"""Factory — Instanciation unique des 5 agents JARVIS (Composition Root des agents).

Responsabilité unique (SRP) : construire et câbler les 5 agents concrets à
partir des services injectés. Aucun comportement métier ici.

Mapping clé → profil (single source of truth du registre d'agents) :
  - cyber    → CyberAgent  (profil datasecu, logique dédiée)
  - dev      → GenericAgent (profil techlead)
  - network  → GenericAgent (profil devops)
  - hardware → GenericAgent (profil orchestrateur)
  - vision   → VisionAgent  (profil designer texte ; image → OCR RapidOCR, pas de LLM multimodal)

NOTE (dette métier, non corrigée ici) : les ``domain_prompt`` courts passés
aux GenericAgent court-circuitent le ``system_prompt`` riche du profil JSON
(``config/agent_profiles.json``) via ``default_prompt`` dans
``BaseAgent._build_messages``. C'est un comportement documenté, pas un bug —
mais il rend les system_prompts JSON de techlead/devops/orchestrateur
inactifs tant que la factory fournit un domain_prompt non None. À trancher
métier : soit retirer les domain_prompt (le JSON redevient source de vérité),
soit supprimer les system_prompts JSON redondants. Hors périmètre refacto
structurel → laissé tel quel, signalé pour traçabilité.
"""

from __future__ import annotations

from typing import Protocol

from agents.base import BaseAgent
from agents.cyber import CyberAgent
from agents.generic import GenericAgent
from agents.vision import VisionAgent

# ---------------------------------------------------------------------------
# Contrats structurels des services injectés (ISP).
# Union des sous-ensembles réellement consommés par les 3 classes d'agents
# (query + get_active_backend pour tous). VisionAgent n'a plus besoin de
# query_multimodal : l'image passe par RapidOCR (services/ocr.py), pas par
# l'inférence LLM.
# ---------------------------------------------------------------------------


class _InferenceLike(Protocol):
    """Sous-ensemble d'inférence requis pour construire les 5 agents."""

    def query(self, prompt: str, model: str, system: str | None = None) -> str: ...
    def get_active_backend(self) -> str: ...


def create_agents(
    inference_service: _InferenceLike,
    memory_service: object | None,
) -> dict[str, BaseAgent]:
    """Construit le registre des 5 agents.

    ``memory_service`` est propagé aux agents pour compat (non exploité par
    ``run()`` — voir docstrings agents). Typé ``object | None`` car aucun
    port n'est consommé : le cast explicite serait requis pour l'utiliser.
    """
    return {
        "cyber": CyberAgent(inference_service, memory_service),
        "dev": GenericAgent(
            inference_service,
            memory_service,
            profile_key="techlead",
            domain_prompt="Expert scripting et développement.",
        ),
        "network": GenericAgent(
            inference_service,
            memory_service,
            profile_key="devops",
            domain_prompt="Expert réseaux.",
        ),
        "hardware": GenericAgent(
            inference_service,
            memory_service,
            profile_key="orchestrateur",
            domain_prompt=(
                "Expert matériel. Tu réponds aux questions de diagnostic "
                "matériel/processus. "
                "Les outils de diagnostic (smartctl, psinfo, psloglist, handle, "
                "psping, psservice, witr) se déclenchent AUTOMATIQUEMENT "
                "si ta demande contient les mots-clés correspondants "
                "(ex: 'disque', 'pourquoi ce processus', 'service', 'ping') "
                "ET si le binaire est déployé sur cette installation. "
                "La liste des outils disponibles avec leur statut est fournie "
                "dans le prompt via la Toolbox. "
                "Si aucun résultat d'outil n'est fourni dans le contexte, "
                "n'invente PAS d'outil : indique honnêtement que l'outil "
                "n'est pas déployé et propose les commandes Windows natives : "
                "`netstat -ano | findstr :PORT` pour les ports, "
                "`Get-Process -Name NOM` pour les processus, "
                "`Get-Service -Name NOM` pour les services."
            ),
        ),
        "vision": VisionAgent(inference_service, memory_service),
    }


__all__ = ["create_agents"]
