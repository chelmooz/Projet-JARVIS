"""Constantes partagées — Limites, version, backend, feedback, launcher.

Chemins délégués à config.paths (compat ascendante via alias PROJECT_DIR).
Toutes les constantes sont immuables au niveau module.

NOTE: Ce module est une façade. Les constantes sont regroupées par domaine
mais restent dans un seul fichier pour éviter de casser les imports existants.
À terme, découper en config/limits.py, config/backend.py, config/feedback.py,
config/launcher.py, config/runtime.py avec ré-exports ici.
"""

from __future__ import annotations

import os
from types import MappingProxyType
from typing import Final

from config.paths import CONFIG_DIR, LOGS_DIR, MEMORY_DIR, ROOT, STATIC_DIR

# ---------------------------------------------------------------------------
# Compat ascendante (deprecated — utiliser config.paths.ROOT directement)
# ---------------------------------------------------------------------------

PROJECT_DIR: Final = ROOT  # Alias legacy, ne pas utiliser dans le nouveau code.

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

VERSION: Final[str] = "5.4"

# ---------------------------------------------------------------------------
# Limites métier
# ---------------------------------------------------------------------------

MAX_HABITS: Final[int] = 200
MAX_LOG_ENTRIES: Final[int] = 500
MAX_QUERIES: Final[int] = 1000
MAX_VECTOR_CACHE: Final[int] = 32
MAX_BODY_SIZE: Final[int] = 10 * 1024 * 1024  # 10 Mo
MAX_CONVERSATION_MESSAGES: Final[int] = 200  # Fenêtre glissante par conversation.
AGENT_TIMEOUT_SECONDS: Final[int] = 120  # Garde-fou wall-clock par agent.
MAX_VECTOR_DOCS: Final[int] = 5000  # Borne de l'index vectoriel sur clef USB.
MAX_FIND_FILES: Final[int] = 1000  # Borne des résultats de find_files.
EMBEDDING_DIM: Final[int] = 768  # Dimension des embeddings nomic-embed-text-v2-moe.

# ---------------------------------------------------------------------------
# Backend par défaut
# ---------------------------------------------------------------------------

DEFAULT_MODEL: Final[str] = "qwen2.5:7b"
DEFAULT_BACKEND: Final[str] = "ollama"
OLLAMA_VERSION: Final[str] = "0.30.10"  # Version pinnée pour déterminisme.

# ---------------------------------------------------------------------------
# Mémoire auto-améliorante (feedback)
# ---------------------------------------------------------------------------

FEEDBACK_WEIGHTS: Final[MappingProxyType[str, float]] = MappingProxyType({
    "copy": 0.3,
    "edit": 0.5,
    "revisit": 0.05,
    "regenerate": -0.3,
    "delete_conv": -1.0,
})

WEIGHT_MIN: Final[float] = -5.0
WEIGHT_MAX: Final[float] = 5.0
RECENCY_DECAY: Final[float] = 0.05  # Perte 5 % par heure, plancher 0.5 après ~10h.

if not (WEIGHT_MIN < WEIGHT_MAX):
    raise ValueError(f"WEIGHT_MIN ({WEIGHT_MIN}) must be < WEIGHT_MAX ({WEIGHT_MAX})")

# ---------------------------------------------------------------------------
# Consolidation hors ligne
# ---------------------------------------------------------------------------

CONSOLIDATE_DEDUP_SIMILARITY: Final[float] = 0.98
CONSOLIDATE_PRUNE_WEIGHT: Final[float] = -2.0
CONSOLIDATE_GRACE_HOURS: Final[int] = 720  # 30 jours.
CONSOLIDATE_MAX_ITER: Final[int] = 1000  # Garde-fou O(n²) time-box.

# ---------------------------------------------------------------------------
# Launcher timeouts (infrastructure)
# ---------------------------------------------------------------------------

LAUNCHER_KILL_DELAY: Final[int] = 1
LAUNCHER_PORT_POLL_MAX: Final[int] = 10
LAUNCHER_PORT_POLL_SLEEP: Final[float] = 0.5
LAUNCHER_START_DELAY: Final[int] = 2
LAUNCHER_PROCESS_WAIT: Final[int] = 3
LAUNCHER_MONITOR_SLEEP: Final[int] = 1
LAUNCHER_RESTART_DELAY: Final[int] = 3
LAUNCHER_POLL_SLEEP: Final[int] = 1
LAUNCHER_URLOPEN_TIMEOUT: Final[int] = 2
LAUNCHER_PIP_TIMEOUT: Final[int] = 10
LAUNCHER_INSTALL_TIMEOUT: Final[int] = 60
LAUNCHER_WAIT_TIMEOUT: Final[int] = 120
LAUNCHER_DOWNLOAD_TIMEOUT: Final[int] = 600  # Binaires 300-600 Mo.

# ---------------------------------------------------------------------------
# Helpers de parsing d'environnement (validation + fallback)
# ---------------------------------------------------------------------------


def _get_env_int(key: str, default: int) -> int:
    """Lit une variable d'env entière avec fallback gracieux."""
    raw = os.environ.get(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Lit une variable d'env booléenne (1/true/yes → True)."""
    raw = os.environ.get(key, "").lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes")


def _get_env_str(key: str, default: str) -> str:
    """Lit une variable d'env string avec fallback."""
    return os.environ.get(key, default) or default


# ---------------------------------------------------------------------------
# Runtime (surchargeable via .env ou variables système)
# NOTE: Ces valeurs sont figées au premier import. Pour un rechargement
# à chaud, utiliser config.reload() ou redémarrer le processus.
# ---------------------------------------------------------------------------

JARVIS_PORT: Final[int] = _get_env_int("JARVIS_PORT", 8000)
JARVIS_LOG_LEVEL: Final[str] = _get_env_str("JARVIS_LOG_LEVEL", "INFO").upper()
JARVIS_DEV: Final[bool] = _get_env_bool("JARVIS_DEV", False)
JARVIS_LOW_IO: Final[bool] = _get_env_bool("JARVIS_LOW_IO", False)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ORIGIN: Final[str] = _get_env_str("CORS_ORIGIN", "http://localhost:3000")

# ---------------------------------------------------------------------------
# Cache & Recherche (profil low I/O)
# ---------------------------------------------------------------------------

VECTOR_CACHE_SIZE_NORMAL: Final[int] = MAX_VECTOR_CACHE
VECTOR_CACHE_SIZE_LOW: Final[int] = 8

DEFAULT_TOP_K: Final[int] = 5
DEFAULT_TOP_K_LOW: Final[int] = 3


def vector_cache_size() -> int:
    """Taille du cache vectoriel selon le profil (low I/O => plus petit)."""
    return VECTOR_CACHE_SIZE_LOW if JARVIS_LOW_IO else VECTOR_CACHE_SIZE_NORMAL


def default_top_k() -> int:
    """Top-k de recherche par défaut selon le profil."""
    return DEFAULT_TOP_K_LOW if JARVIS_LOW_IO else DEFAULT_TOP_K


# ---------------------------------------------------------------------------
# Intervalles de rafraîchissement
# ---------------------------------------------------------------------------

REFRESH_INTERVAL: Final[int] = 30  # Secondes entre chaque refresh du cache de statut.
WARMUP_DELAY: Final[int] = 5  # Secondes de délai avant le warmup.

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    # Compat
    "PROJECT_DIR",
    # Chemins (ré-export depuis config.paths)
    "CONFIG_DIR",
    "LOGS_DIR",
    "MEMORY_DIR",
    "STATIC_DIR",
    # Version
    "VERSION",
    # Limites
    "MAX_HABITS",
    "MAX_LOG_ENTRIES",
    "MAX_QUERIES",
    "MAX_VECTOR_CACHE",
    "MAX_BODY_SIZE",
    "MAX_CONVERSATION_MESSAGES",
    "AGENT_TIMEOUT_SECONDS",
    "MAX_VECTOR_DOCS",
    "MAX_FIND_FILES",
    "EMBEDDING_DIM",
    # Backend
    "DEFAULT_MODEL",
    "DEFAULT_BACKEND",
    "OLLAMA_VERSION",
    # Feedback
    "FEEDBACK_WEIGHTS",
    "WEIGHT_MIN",
    "WEIGHT_MAX",
    "RECENCY_DECAY",
    # Consolidation
    "CONSOLIDATE_DEDUP_SIMILARITY",
    "CONSOLIDATE_PRUNE_WEIGHT",
    "CONSOLIDATE_GRACE_HOURS",
    "CONSOLIDATE_MAX_ITER",
    # Launcher
    "LAUNCHER_KILL_DELAY",
    "LAUNCHER_PORT_POLL_MAX",
    "LAUNCHER_PORT_POLL_SLEEP",
    "LAUNCHER_START_DELAY",
    "LAUNCHER_PROCESS_WAIT",
    "LAUNCHER_MONITOR_SLEEP",
    "LAUNCHER_RESTART_DELAY",
    "LAUNCHER_POLL_SLEEP",
    "LAUNCHER_URLOPEN_TIMEOUT",
    "LAUNCHER_PIP_TIMEOUT",
    "LAUNCHER_INSTALL_TIMEOUT",
    "LAUNCHER_WAIT_TIMEOUT",
    "LAUNCHER_DOWNLOAD_TIMEOUT",
    # Runtime
    "JARVIS_PORT",
    "JARVIS_LOG_LEVEL",
    "JARVIS_DEV",
    "JARVIS_LOW_IO",
    # CORS
    "CORS_ORIGIN",
    # Cache
    "VECTOR_CACHE_SIZE_NORMAL",
    "VECTOR_CACHE_SIZE_LOW",
    "DEFAULT_TOP_K",
    "DEFAULT_TOP_K_LOW",
    "vector_cache_size",
    "default_top_k",
    # Refresh
    "REFRESH_INTERVAL",
    "WARMUP_DELAY",
]
