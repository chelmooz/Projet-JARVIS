"""Constantes partagées — Limites, version, backend par défaut.

Chemins : délégués à config.paths (compat ascendante via alias PROJECT_DIR).
"""
import os

from config.paths import CONFIG_DIR, LOGS_DIR, MEMORY_DIR, ROOT, STATIC_DIR

PROJECT_DIR = ROOT
VERSION = "5.4"

# --- Limites ---
MAX_HABITS = 200         # Nombre max d'entrées d'habitudes
MAX_LOG_ENTRIES = 500    # Nombre max d'entrées dans le fichier de log
MAX_QUERIES = 1000       # Nombre max de requêtes trackées dans analytics
MAX_VECTOR_CACHE = 32    # Taille du cache LRU des recherches vectorielles
MAX_BODY_SIZE = 10 * 1024 * 1024  # Taille max du body HTTP (10 Mo)
MAX_CONVERSATION_MESSAGES = 200  # Garde les 200 derniers messages par conversation
                                 # (fenetre glissante : evite un JSON qui grossit
                                 # indéfiniment sur cle USB lente).
AGENT_TIMEOUT_SECONDS = 120    # Garde-fou wall-clock par agent (prompt+toolbox+LLM)

# --- Backend par défaut ---
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_BACKEND = "ollama"

# --- Mémoire auto-améliorante (feedback) ---
# Poids implicites des signaux (externes, ajustables sans toucher au code métier).
FEEDBACK_WEIGHTS = {
    "copy": 0.3,           # l'utilisateur réutilise la réponse
    "edit": 0.5,           # l'utilisateur édite/adapte la réponse
    "revisit": 0.05,        # relecture d'une conversation (engagement faible)
    "regenerate": -0.3,     # l'utilisateur demande une autre réponse
    "delete_conv": -1.0,    # suppression de la conversation (signal fort négatif)
}
# Borne de clamp du poids d'un souvenir vectoriel.
WEIGHT_MIN = -5.0
WEIGHT_MAX = 5.0
# Décroissance de la récence dans la recherche pondérée (Étape 4).
# recency_factor = max(0.5, 1.0 - RECENCY_DECAY * age_hours)
# → perte 5 % par heure, plancher 0.5 après ~10h. Ajustable sans toucher au code métier.
RECENCY_DECAY = 0.05

# --- Consolidation hors ligne (Étape 5) ---
# Seuil de similarité cosinus pour considérer deux embeddings comme quasi-identiques.
CONSOLIDATE_DEDUP_SIMILARITY = 0.98
# Seuil de poids en dessous duquel un souvenir est éligible à la purge.
CONSOLIDATE_PRUNE_WEIGHT = -2.0
# Délai de grâce (heures) avant qu'un souvenir à poids bas ne soit purgé.
CONSOLIDATE_GRACE_HOURS = 720  # 30 jours
# Nombre max d'itérations (garde-fou O(n²) time-box).
CONSOLIDATE_MAX_ITER = 1000
# Nombre maximum de documents conservés dans l'index vectoriel. Au-delà,
# consolidate() purge les moins pertinents (poids puis ancienneté) pour borner
# la taille du store sur clef USB et éviter une croissance infinie.
MAX_VECTOR_DOCS = 5000
# Nombre maximum de resultats retournes par find_files (evite de scanner/
# retourner des millions d'entrees sur une clef USB).
MAX_FIND_FILES = 1000

# --- Launcher timeouts ---
LAUNCHER_KILL_DELAY = 1
LAUNCHER_PORT_POLL_MAX = 10  # Nombre max de tentatives pour verifier si le port est libre
LAUNCHER_PORT_POLL_SLEEP = 0.5  # Delai entre chaque tentative (secondes)
LAUNCHER_START_DELAY = 2
LAUNCHER_PROCESS_WAIT = 3
LAUNCHER_MONITOR_SLEEP = 1
LAUNCHER_RESTART_DELAY = 3
LAUNCHER_POLL_SLEEP = 1
LAUNCHER_URLOPEN_TIMEOUT = 2
LAUNCHER_PIP_TIMEOUT = 10
LAUNCHER_INSTALL_TIMEOUT = 60
LAUNCHER_WAIT_TIMEOUT = 120
LAUNCHER_DOWNLOAD_TIMEOUT = 600  # Augmente a 600s pour binaires 300-600 Mo (audit D10)

# --- Ollama version (pingee pour determinisme) ---
OLLAMA_VERSION = "0.30.10"  # Version connue stable, evite 'latest' non deterministe

# --- Environnement (surchargeable via .env ou variables système) ---
JARVIS_PORT = int(os.environ.get("JARVIS_PORT", "8000"))
JARVIS_LOG_LEVEL = os.environ.get("JARVIS_LOG_LEVEL", "INFO").upper()
JARVIS_DEV = os.environ.get("JARVIS_DEV", "").lower() in ("1", "true", "yes")
# Profil low I/O / low VRAM : reduit les acces disque (cache vectoriel plus petit,
# moins de resultats par defaut) pour les machines sur cle USB lente ou peu de RAM.
JARVIS_LOW_IO = os.environ.get("JARVIS_LOW_IO", "").lower() in ("1", "true", "yes")

# --- CORS ---
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")

# Tailles de cache adaptees au profil
VECTOR_CACHE_SIZE_NORMAL = MAX_VECTOR_CACHE
VECTOR_CACHE_SIZE_LOW = 8

DEFAULT_TOP_K = 5
DEFAULT_TOP_K_LOW = 3

# --- Intervalles de rafraichissement ---
REFRESH_INTERVAL = 30  # secondes entre chaque refresh du cache de statut
WARMUP_DELAY = 5  # secondes de delai avant le warmup


def vector_cache_size() -> int:
    """Taille du cache vectoriel selon le profil (low I/O => plus petit)."""
    return VECTOR_CACHE_SIZE_LOW if JARVIS_LOW_IO else VECTOR_CACHE_SIZE_NORMAL


def default_top_k() -> int:
    """Top-k de recherche par defaut selon le profil."""
    return DEFAULT_TOP_K_LOW if JARVIS_LOW_IO else DEFAULT_TOP_K

__all__ = [
    "PROJECT_DIR",
    "STATIC_DIR",
    "CONFIG_DIR",
    "MEMORY_DIR",
    "LOGS_DIR",
    "VERSION",
    "MAX_HABITS",
    "MAX_LOG_ENTRIES",
    "MAX_QUERIES",
    "MAX_VECTOR_CACHE",
    "MAX_BODY_SIZE",
    "MAX_CONVERSATION_MESSAGES",
    "AGENT_TIMEOUT_SECONDS",
    "DEFAULT_MODEL",
    "DEFAULT_BACKEND",
    "FEEDBACK_WEIGHTS",
    "WEIGHT_MIN",
    "WEIGHT_MAX",
    "RECENCY_DECAY",
    "CONSOLIDATE_DEDUP_SIMILARITY",
    "CONSOLIDATE_PRUNE_WEIGHT",
    "CONSOLIDATE_GRACE_HOURS",
    "CONSOLIDATE_MAX_ITER",
    "MAX_VECTOR_DOCS",
    "MAX_FIND_FILES",
    "JARVIS_PORT",
    "JARVIS_LOG_LEVEL",
    "JARVIS_DEV",
    "JARVIS_LOW_IO",
    "CORS_ORIGIN",
    "VECTOR_CACHE_SIZE_LOW",
    "DEFAULT_TOP_K",
    "DEFAULT_TOP_K_LOW",
    "REFRESH_INTERVAL",
    "WARMUP_DELAY",
    "vector_cache_size",
    "default_top_k",
    "LAUNCHER_KILL_DELAY",
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
    "OLLAMA_VERSION",
    "LAUNCHER_PORT_POLL_MAX",
    "LAUNCHER_PORT_POLL_SLEEP",
    "VECTOR_CACHE_SIZE_NORMAL",
]
