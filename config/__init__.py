"""Configuration JARVIS — Chargement typé et validation des fichiers JSON.

Expose une API immuable et validée pour accéder aux configurations :
- agent_profiles.json   : profils d'équipe (orchestrateur, techlead, devops, designer, datasecu)
- model_preferences.json: mapping modèles → profils → agents
- cyber_workflows.json  : workflows cybersec (NVISO + natifs)
- components.json       : versions et assets pour le downloader
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Erreurs
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Erreur de chargement ou de validation de configuration."""


# ---------------------------------------------------------------------------
# Dataclasses de configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentProfileConfig:
    """Profil d'équipe (orchestrateur, techlead, devops, designer, datasecu)."""
    key: str
    name: str
    title: str
    model: str
    system_prompt: str = ""
    skills: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelPreference:
    """Mapping modèle → profil → agent."""
    model: str
    profile: str
    agent: str
    priority: int = 0


@dataclass(frozen=True)
class CyberWorkflow:
    """Workflow cybersec (NVISO ou natif)."""
    id: str
    name: str
    description: str
    steps: tuple[dict[str, Any], ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentAsset:
    """Asset téléchargeable (binaire, modèle, etc.)."""
    name: str
    version: str
    url: str
    sha256: str | None = None
    platform: str = "all"


@dataclass(frozen=True)
class ComponentsConfig:
    """Versions et assets pour le downloader."""
    ollama_version: str
    python_version: str
    assets: tuple[ComponentAsset, ...] = ()


# ---------------------------------------------------------------------------
# Loader générique
# ---------------------------------------------------------------------------

def _load_json(filename: str) -> Any:
    """Charge un fichier JSON depuis le dossier config/.

    Raises:
        ConfigError: Si le fichier est absent ou invalide.
    """
    path = _CONFIG_DIR / filename
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Cannot read {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Accès typés (avec cache module-level)
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}


def get_agent_profiles() -> tuple[AgentProfileConfig, ...]:
    """Retourne les 5 profils d'équipe validés."""
    if "agent_profiles" not in _cache:
        raw = _load_json("agent_profiles.json")
        profiles = tuple(
            AgentProfileConfig(
                key=p["key"],
                name=p["name"],
                title=p["title"],
                model=p["model"],
                system_prompt=p.get("system_prompt", ""),
                skills=tuple(p.get("skills", [])),
            )
            for p in raw
        )
        _cache["agent_profiles"] = profiles
    return _cache["agent_profiles"]


def get_model_preferences() -> tuple[ModelPreference, ...]:
    """Retourne le mapping modèles → profils → agents."""
    if "model_preferences" not in _cache:
        raw = _load_json("model_preferences.json")
        prefs = tuple(
            ModelPreference(
                model=m["model"],
                profile=m["profile"],
                agent=m["agent"],
                priority=m.get("priority", 0),
            )
            for m in raw
        )
        _cache["model_preferences"] = prefs
    return _cache["model_preferences"]


def get_cyber_workflows() -> tuple[CyberWorkflow, ...]:
    """Retourne les workflows cybersec validés."""
    if "cyber_workflows" not in _cache:
        raw = _load_json("cyber_workflows.json")
        workflows = tuple(
            CyberWorkflow(
                id=w["id"],
                name=w["name"],
                description=w.get("description", ""),
                steps=tuple(w.get("steps", [])),
                tags=tuple(w.get("tags", [])),
            )
            for w in raw
        )
        _cache["cyber_workflows"] = workflows
    return _cache["cyber_workflows"]


def get_components() -> ComponentsConfig:
    """Retourne la config des composants téléchargeables."""
    if "components" not in _cache:
        raw = _load_json("components.json")
        assets = tuple(
            ComponentAsset(
                name=a["name"],
                version=a["version"],
                url=a["url"],
                sha256=a.get("sha256"),
                platform=a.get("platform", "all"),
            )
            for a in raw.get("assets", [])
        )
        _cache["components"] = ComponentsConfig(
            ollama_version=raw["ollama_version"],
            python_version=raw["python_version"],
            assets=assets,
        )
    return _cache["components"]


def reload() -> None:
    """Invalide le cache (utile pour les tests ou le rechargement à chaud)."""
    _cache.clear()
    logger.info("Config cache invalidated")


__all__ = [
    "ConfigError",
    "AgentProfileConfig",
    "ModelPreference",
    "CyberWorkflow",
    "ComponentAsset",
    "ComponentsConfig",
    "get_agent_profiles",
    "get_model_preferences",
    "get_cyber_workflows",
    "get_components",
    "reload",
]
