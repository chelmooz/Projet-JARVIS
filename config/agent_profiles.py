"""AgentProfiles — Modèle configuré par agent (config/agent_profiles.json).

``agent_profiles.json`` a la forme ``{"profiles": {"<profile_key>": {"model": ...}}}``
: les clés sont les PROFILS (orchestrateur, techlead, devops, designer, datasecu).
Les clés de ROUTAGE utilisées par le chat (/api/jarvis, router fallback) sont les
noms d'agents (dev, network, hardware, cyber, vision) — même mapping que
agents/factory.py. ``model_for_agent`` résout les deux formes grâce à
``AGENT_TO_PROFILE``. Ce module ne duplique pas la logique riche de
agents/base.py::_load_profile (cache mtime, verrou, skills) : il expose
seulement l'information minimale nécessaire aux points d'appel qui n'ont pas
d'instance BaseAgent sous la main, comme services.pipeline_steps.select_model.

Responsabilité unique : agent_key -> modèle configuré (ou None).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from config.paths import PROFILES_FILE

_logger = logging.getLogger(__name__)

# Clés de routage (chat / router / pipeline) -> profil JSON associé.
# Single source of truth : agents/factory.py (create_agents/agent_key).
AGENT_TO_PROFILE: dict[str, str] = {
    "cyber": "datasecu",
    "dev": "techlead",
    "network": "devops",
    "hardware": "orchestrateur",
    "vision": "designer",
}


def model_for_agent(agent_key: str) -> str | None:
    """Retourne le modèle configuré pour ``agent_key``, ou None si absent.

    ``agent_key`` peut être une clé de routage (dev, network, hardware, cyber,
    vision) ou une clé de profil (techlead, devops, orchestrateur, datasecu,
    designer) — les deux formes sont résolues.

    Dégradation gracieuse : fichier manquant, JSON corrompu ou agent
    inconnu retournent tous None plutôt que de lever — l'appelant décide
    du fallback (jamais de crash pour un souci de config).
    """
    try:
        with Path(PROFILES_FILE).open(encoding="utf-8") as handle:
            profiles = json.load(handle).get("profiles", {})
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("agent_profiles.json illisible (%s): %s", PROFILES_FILE, exc)
        return None
    profile_key = AGENT_TO_PROFILE.get(agent_key, agent_key)
    return profiles.get(profile_key, {}).get("model")


__all__ = ["model_for_agent"]
