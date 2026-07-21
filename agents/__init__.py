"""Agents — Implémentations des 5 profils JARVIS.

Chaque agent correspond à un profil défini dans config/agent_profiles.json :
  - dev       (techlead)      : scripts, code, debug
  - network   (devops)        : diagnostique réseau, connectivité
  - hardware  (orchestrateur) : matériel, drivers, BIOS
  - cyber     (datasecu)      : cybersecurité, workflows NVISO
  - vision    (designer)      : analyse visuelle, screenshot

Les agents dev, network, hardware sont des GenericAgent configurés par profil.
CyberAgent et VisionAgent ont des spécialisations.
"""

from agents.base import BaseAgent
from agents.cyber import CyberAgent
from agents.factory import create_agents
from agents.generic import GenericAgent
from agents.vision import VisionAgent

__all__ = [
    "BaseAgent",
    "GenericAgent",
    "CyberAgent",
    "VisionAgent",
    "create_agents",
]
