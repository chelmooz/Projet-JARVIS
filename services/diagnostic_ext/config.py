"""Configuration — constantes, helpers, chargement YAML des outils."""

from __future__ import annotations

import os
import sys
from typing import Any

import yaml

from config.constants import PROJECT_DIR
from services.diagnostic_ext.exceptions import DiagnosticExtError

CONFIG_PATH: str = os.path.join(PROJECT_DIR, "config", "diagnostic_tools.yaml")
BIN_DIR: str = os.path.join(PROJECT_DIR, "bin", "diagnostic")
CONSENT_FILE: str = os.path.join(PROJECT_DIR, "config", ".diagnostic_consent")


def default_smart_device() -> str:
    """Retourne le device par défaut pour smartctl selon la plateforme."""
    if sys.platform == "win32":
        return "physicaldrive0"
    if sys.platform == "darwin":
        return "disk0"
    return "/dev/sda"


def load_config(config_path: str) -> dict[str, Any]:
    """Charge la configuration YAML des outils de diagnostic.

    Args:
        config_path: Chemin vers le fichier YAML.

    Returns:
        Dictionnaire de configuration.

    Raises:
        DiagnosticExtError: Si le fichier est introuvable ou invalide.
    """
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError) as e:
        raise DiagnosticExtError(f"Impossible de charger {config_path}: {e}") from e


def get_tools_config(config: dict[str, Any]) -> dict[str, Any]:
    """Extrait la section 'tools' de la configuration globale."""
    tools = config.get("tools")
    return tools if isinstance(tools, dict) else {}


__all__ = [
    "CONFIG_PATH",
    "BIN_DIR",
    "CONSENT_FILE",
    "default_smart_device",
    "load_config",
    "get_tools_config",
]
