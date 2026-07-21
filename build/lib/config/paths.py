"""Chemins centralisés du projet — Single Point of Truth.

Remplace les définitions dupliquées de chemins dans 17+ fichiers.
Tous les chemins sont dérivés de ROOT (détection automatique).
Plateformes supportées : windows, linux, darwin.
"""
import os
import platform

# --- Racine du projet (auto-détectée) ---
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Plateforme ---
SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == "windows"

# --- Répertoires racine ---
BIN_DIR = os.path.join(ROOT, "bin")
CONFIG_DIR = os.path.join(ROOT, "config")
MODELS_DIR = os.path.join(ROOT, "models")
PORTABLE_DIR = os.path.join(ROOT, "portable_python")
STATIC_DIR = os.path.join(ROOT, "static")
MEMORY_DIR = os.path.join(ROOT, "memory")
LOGS_DIR = os.path.join(ROOT, "logs")

LIB_DIR = os.path.join(ROOT, "lib")

# --- Sous-répertoires ---
BIN_WIN = os.path.join(BIN_DIR, "win")
BIN_LINUX = os.path.join(BIN_DIR, "linux")
BIN_MAC = os.path.join(BIN_DIR, "mac")
BIN_DIAGNOSTIC = os.path.join(BIN_DIR, "diagnostic")
MODELS_OLLAMA = os.path.join(MODELS_DIR, "ollama")
OLLAMA_LIB = os.path.join(LIB_DIR, "ollama")
PID_DIR = os.path.join(MEMORY_DIR, "pids")
PIPELINES_DIR = os.path.join(CONFIG_DIR, "pipelines")

# --- Fichiers de configuration ---
ADAPTERS_CONFIG = os.path.join(CONFIG_DIR, "adapters.yaml")
PREFERENCES_FILE = os.path.join(CONFIG_DIR, "model_preferences.json")
PROFILES_FILE = os.path.join(CONFIG_DIR, "agent_profiles.json")
ROUTING_CONFIG = os.path.join(CONFIG_DIR, "agent_routing.yaml")
TRIGGERS_CONFIG = os.path.join(CONFIG_DIR, "toolbox_triggers.yaml")
CYBER_KEYWORDS_CONFIG = os.path.join(CONFIG_DIR, "cyber_workflow_keywords.yaml")
DIAGNOSTIC_CONFIG = os.path.join(CONFIG_DIR, "diagnostic_tools.yaml")
CONSENT_FILE = os.path.join(CONFIG_DIR, ".diagnostic_consent")
REQUIREMENTS_FILE = os.path.join(ROOT, "requirements.txt")
CYBER_WORKFLOWS_CONFIG = os.path.join(CONFIG_DIR, "cyber_workflows.json")
SKILLS_CONFIG = os.path.join(CONFIG_DIR, "skills.json")

# --- Fichiers de logs ---
LOG_FILE = os.path.join(LOGS_DIR, "api.json")


# --- Sous-répertoires portable Python ---
PORTABLE_WIN = os.path.join(PORTABLE_DIR, "win")
PORTABLE_LINUX = os.path.join(PORTABLE_DIR, "linux")
PORTABLE_MAC = os.path.join(PORTABLE_DIR, "mac")

# --- Binaires (plateforme dépendante) ---
if IS_WINDOWS:
    OLLAMA_EXE = os.path.join(BIN_WIN, "ollama.exe")
    PORTABLE_PYTHON_EXE = os.path.join(PORTABLE_WIN, "python.exe")
elif SYSTEM == "darwin":
    OLLAMA_EXE = os.path.join(BIN_MAC, "ollama")
    PORTABLE_PYTHON_EXE = os.path.join(PORTABLE_MAC, "bin", "python3")
else:
    OLLAMA_EXE = os.path.join(BIN_LINUX, "ollama")
    PORTABLE_PYTHON_EXE = os.path.join(PORTABLE_LINUX, "python3")

# Port custom JARVIS (≠ 11434) pour ne pas confliter avec une instance Ollama systeme deja lancee
OLLAMA_PORT = 11436
OLLAMA_HOST = f"127.0.0.1:{OLLAMA_PORT}"
