"""Service de routage — Selection de l'agent JARVIS par analyse de mots-clés.

La configuration (préfixes, mots-clés, fallback) vit dans
``config/agent_routing.yaml`` (ROUTING_CONFIG) : source de vérité unique,
plus aucun mapping hardcodé. Ajouter un agent ou un mot-clé = éditer le YAML.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from config.paths import ROUTING_CONFIG
from models import Task

_logger = logging.getLogger("jarvis.router")

DEFAULT_FALLBACK = "dev"


@dataclass(frozen=True)
class AgentRoutingConfig:
    """Configuration de routage (immutable, partage multi-thread safe)."""

    prefix_map: dict[str, str]
    keyword_map: dict[str, list[str]]
    fallback: str = DEFAULT_FALLBACK


def load_routing_config(path: str | Path = ROUTING_CONFIG) -> AgentRoutingConfig:
    """Charge la configuration de routage depuis le YAML.

    Dégradation gracieuse : YAML absent ou corrompu → config vide avec
    fallback par défaut (loggé en warning, jamais de crash au démarrage).
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        _logger.warning("Config routage indisponible (%s): %s", path, exc)
        return AgentRoutingConfig(prefix_map={}, keyword_map={})
    return AgentRoutingConfig(
        prefix_map=dict(data.get("prefix_map", {})),
        keyword_map={
            agent: list(keywords)
            for agent, keywords in data.get("keyword_map", {}).items()
        },
        fallback=data.get("fallback", DEFAULT_FALLBACK),
    )


class AgentRouter:
    """Router détermine quel agent (cyber, dev, network, hardware, vision)
    doit traiter une tâche en fonction de son contenu textuel.

    Stratégie (par ordre de priorité) :
      1. Préfixe explicite (@cyber, @dev, etc.)
      2. Score de mots-clés (agent avec le plus de matches gagne)
      3. Agent par défaut : "dev"
    """

    def __init__(self, config: AgentRoutingConfig | None = None) -> None:
        self._config = config or load_routing_config()

    def select_agent(self, task_text: str | Task) -> str:
        """Retourne la clé agent la plus pertinente pour la tâche donnée."""
        if isinstance(task_text, Task):
            task_text = task_text.text
        lower = task_text.lower().strip()
        if not lower:
            return self._config.fallback

        # Priorité 1 : préfixe explicite @agent
        for prefix, agent in self._config.prefix_map.items():
            if lower.startswith(prefix):
                return agent

        # Priorité 2 : score de mots-clés (agent avec le plus de hits)
        scores = {
            agent: sum(1 for keyword in keywords if keyword in lower)
            for agent, keywords in self._config.keyword_map.items()
        }
        best_agent = max(scores, key=scores.get) if scores else None
        if best_agent is not None and scores[best_agent] > 0:
            return best_agent

        # Priorité 3 : fallback par défaut
        return self._config.fallback


__all__ = ["AgentRouter", "AgentRoutingConfig", "load_routing_config"]
