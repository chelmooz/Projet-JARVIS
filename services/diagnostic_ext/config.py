"""Configuration — constantes, helpers, chargement YAML des outils."""
import os
import sys

import yaml

from config.constants import PROJECT_DIR
from services.diagnostic_ext.exceptions import DiagnosticExtError

CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "diagnostic_tools.yaml")
BIN_DIR = os.path.join(PROJECT_DIR, "bin", "diagnostic")
CONSENT_FILE = os.path.join(PROJECT_DIR, "config", ".diagnostic_consent")


def default_smart_device() -> str:
    if sys.platform == "win32":
        return "physicaldrive0"
    if sys.platform == "darwin":
        return "disk0"
    return "/dev/sda"


def load_config(config_path: str) -> dict:
    try:
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise DiagnosticExtError(f"Impossible de charger {config_path}: {e}")


def get_tools_config(config: dict) -> dict:
    return config.get("tools", {})
