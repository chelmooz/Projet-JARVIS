"""Agents — Implémentations des 5 profils JARVIS.

Chaque agent correspond à un profil défini dans config/agent_profiles.json :
  - dev       (techlead)      : scripts, code, debug
  - network   (devops)        : diagnostic réseau, connectivité
  - hardware  (orchestrateur) : matériel, drivers, BIOS
  - cyber     (datasecu)      : cybersécurité, workflows NVISO
  - vision    (designer)      : analyse visuelle, screenshot

Les agents dev, network, hardware sont des GenericAgent configurés par profil.
CyberAgent et VisionAgent ont des spécialisations.
"""

from .base import BaseAgent
from .cyber import CyberAgent
from .factory import create_agents
from .generic import GenericAgent
from .vision import VisionAgent

__all__ = [
    "BaseAgent",
    "GenericAgent",
    "CyberAgent",
    "VisionAgent",
    "create_agents",
]
