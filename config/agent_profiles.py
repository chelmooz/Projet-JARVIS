"""AgentProfiles — Modèle configuré par agent (config/agent_profiles.json).

``agent_profiles.json`` a la forme ``{"profiles": {"<agent_key>": {"model": ...}}}``
(cf. agents/base.py::_load_profile, qui lit le même fichier pour construire les
system prompts). Ce module ne duplique pas cette logique riche (cache mtime,
verrou, skills) : il expose seulement l'information minimale nécessaire aux
points d'appel qui n'ont pas d'instance BaseAgent sous la main, comme
services.pipeline_steps.select_model.

Responsabilité unique : agent_key -> modèle configuré (ou None).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.paths import PROFILES_FILE

_logger = logging.getLogger(__name__)


def model_for_agent(agent_key: str) -> str | None:
    """Retourne le modèle configuré pour ``agent_key``, ou None si absent.

    Dégradation gracieuse : fichier manquant, JSON corrompu ou agent
    inconnu retournent tous None plutôt que de lever — l'appelant décide
    du fallback (jamais de crash LLM pour un souci de config).
    """
    try:
        with Path(PROFILES_FILE).open(encoding="utf-8") as handle:
            profiles = json.load(handle).get("profiles", {})
    except (OSError, json.JSONDecodeError) as exc:
        _logger.warning("agent_profiles.json illisible (%s): %s", PROFILES_FILE, exc)
        return None
    return profiles.get(agent_key, {}).get("model")


__all__ = ["model_for_agent"]
