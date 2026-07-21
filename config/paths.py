"""Chemins centralisés du projet — Single Point of Truth.
Tous les chemins sont dérivés de ROOT (détection automatique via pathlib).
Plateformes supportées : windows, linux, darwin.
"""
from __future__ import annotations

import platform
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Racine du projet (auto-détectée)
# ---------------------------------------------------------------------------
ROOT: Final[Path] = Path(__file__).resolve().parent.parent
if not ROOT.exists():
    raise FileNotFoundError(f"Project root not found: {ROOT}")

# ---------------------------------------------------------------------------
# Plateforme
# ---------------------------------------------------------------------------
SYSTEM: Final[str] = platform.system().lower()
IS_WINDOWS: Final[bool] = SYSTEM == "windows"
IS_MACOS: Final[bool] = SYSTEM == "darwin"
IS_LINUX: Final[bool] = SYSTEM == "linux"

# ---------------------------------------------------------------------------
# Répertoires racine
# ---------------------------------------------------------------------------
BIN_DIR: Final[Path] = ROOT / "bin"
CONFIG_DIR: Final[Path] = ROOT / "config"
MODELS_DIR: Final[Path] = ROOT / "models"
PORTABLE_DIR: Final[Path] = ROOT / "portable_python"
STATIC_DIR: Final[Path] = ROOT / "static"
MEMORY_DIR: Final[Path] = ROOT / "memory"
LOGS_DIR: Final[Path] = ROOT / "logs"
LIB_DIR: Final[Path] = ROOT / "lib"

# ---------------------------------------------------------------------------
# Sous-répertoires binaires (par plateforme)
# ---------------------------------------------------------------------------
BIN_WIN: Final[Path] = BIN_DIR / "win"
BIN_LINUX: Final[Path] = BIN_DIR / "linux"
BIN_MAC: Final[Path] = BIN_DIR / "mac"
BIN_DIAGNOSTIC: Final[Path] = BIN_DIR / "diagnostic"

# ---------------------------------------------------------------------------
# Sous-répertoires modèles & lib
# ---------------------------------------------------------------------------
MODELS_OLLAMA: Final[Path] = MODELS_DIR / "ollama"
OLLAMA_LIB: Final[Path] = LIB_DIR / "ollama"

# ---------------------------------------------------------------------------
# Sous-répertoires mémoire & config
# ---------------------------------------------------------------------------
PID_DIR: Final[Path] = MEMORY_DIR / "pids"
PIPELINES_DIR: Final[Path] = CONFIG_DIR / "pipelines"

# ---------------------------------------------------------------------------
# Fichiers de configuration
# ---------------------------------------------------------------------------
ADAPTERS_CONFIG: Final[Path] = CONFIG_DIR / "adapters.yaml"
PROFILES_FILE: Final[Path] = CONFIG_DIR / "agent_profiles.json"
PREFERENCES_FILE: Final[Path] = CONFIG_DIR / "model_preferences.json"  # <-- AJOUT
ROUTING_CONFIG: Final[Path] = CONFIG_DIR / "agent_routing.yaml"
TRIGGERS_CONFIG: Final[Path] = CONFIG_DIR / "toolbox_triggers.yaml"
CYBER_KEYWORDS_CONFIG: Final[Path] = CONFIG_DIR / "cyber_workflow_keywords.yaml"
DIAGNOSTIC_CONFIG: Final[Path] = CONFIG_DIR / "diagnostic_tools.yaml"
CONSENT_FILE: Final[Path] = CONFIG_DIR / ".diagnostic_consent"
CYBER_WORKFLOWS_CONFIG: Final[Path] = CONFIG_DIR / "cyber_workflows.json"
SKILLS_CONFIG: Final[Path] = CONFIG_DIR / "skills.json"
REQUIREMENTS_FILE: Final[Path] = ROOT / "requirements.txt"

# ---------------------------------------------------------------------------
# Fichiers de logs
# ---------------------------------------------------------------------------
LOG_FILE: Final[Path] = LOGS_DIR / "api.json"

# ---------------------------------------------------------------------------
# Sous-répertoires portable Python (par plateforme)
# ---------------------------------------------------------------------------
PORTABLE_WIN: Final[Path] = PORTABLE_DIR / "win"
PORTABLE_LINUX: Final[Path] = PORTABLE_DIR / "linux"
PORTABLE_MAC: Final[Path] = PORTABLE_DIR / "mac"

# ---------------------------------------------------------------------------
# Binaires plateforme-dépendants (fonctions pour testabilité)
# ---------------------------------------------------------------------------
def get_ollama_exe() -> Path:
    """Retourne le chemin du binaire Ollama pour la plateforme courante."""
    if IS_WINDOWS:
        return BIN_WIN / "ollama.exe"
    if IS_MACOS:
        return BIN_MAC / "ollama"
    return BIN_LINUX / "ollama"

def get_portable_python() -> Path:
    """Retourne le chemin de l'exécutable Python portable pour la plateforme courante."""
    if IS_WINDOWS:
        return PORTABLE_WIN / "python.exe"
    if IS_MACOS:
        return PORTABLE_MAC / "bin" / "python3"
    return PORTABLE_LINUX / "python3"

# Aliases pour compat ascendante (déprécié — utiliser les fonctions ci-dessus).
OLLAMA_EXE: Final[Path] = get_ollama_exe()
PORTABLE_PYTHON_EXE: Final[Path] = get_portable_python()

# ---------------------------------------------------------------------------
# Configuration réseau Ollama (port custom pour éviter conflit système)
# ---------------------------------------------------------------------------
OLLAMA_PORT: Final[int] = 11436
OLLAMA_HOST: Final[str] = f"127.0.0.1:{OLLAMA_PORT}"

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
__all__ = [
    # Racine & plateforme
    "ROOT",
    "SYSTEM",
    "IS_WINDOWS",
    "IS_MACOS",
    "IS_LINUX",
    # Répertoires racine
    "BIN_DIR",
    "CONFIG_DIR",
    "MODELS_DIR",
    "PORTABLE_DIR",
    "STATIC_DIR",
    "MEMORY_DIR",
    "LOGS_DIR",
    "LIB_DIR",
    # Sous-répertoires binaires
    "BIN_WIN",
    "BIN_LINUX",
    "BIN_MAC",
    "BIN_DIAGNOSTIC",
    # Modèles & lib
    "MODELS_OLLAMA",
    "OLLAMA_LIB",
    # Mémoire & config
    "PID_DIR",
    "PIPELINES_DIR",
    # Fichiers de config
    "ADAPTERS_CONFIG",
    "PROFILES_FILE",
    "PREFERENCES_FILE",  # <-- AJOUT
    "ROUTING_CONFIG",
    "TRIGGERS_CONFIG",
    "CYBER_KEYWORDS_CONFIG",
    "DIAGNOSTIC_CONFIG",
    "CONSENT_FILE",
    "CYBER_WORKFLOWS_CONFIG",
    "SKILLS_CONFIG",
    "REQUIREMENTS_FILE",
    # Logs
    "LOG_FILE",
    # Portable Python
    "PORTABLE_WIN",
    "PORTABLE_LINUX",
    "PORTABLE_MAC",
    # Binaires (fonctions + aliases compat)
    "get_ollama_exe",
    "get_portable_python",
    "OLLAMA_EXE",
    "PORTABLE_PYTHON_EXE",
    # Réseau
    "OLLAMA_PORT",
    "OLLAMA_HOST",
]
