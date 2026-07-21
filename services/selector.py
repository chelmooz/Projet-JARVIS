"""Selecteur de modeles — Choisit le meilleur modele disponible pour un agent."""
import json
import os
from collections.abc import Sequence

from config.constants import PROJECT_DIR

# Chemin du fichier de préférences utilisateur (modèle préféré par agent)
PREFERENCES_PATH = os.path.join(PROJECT_DIR, "config", "model_preferences.json")

# Modèles vision supportés (par ordre de préférence décroissant)
VISION_MODELS = ["llama3.2-vision"]

VISION_KEY = "vision"

MODEL_SIZES_PATH = os.path.join(PROJECT_DIR, "config", "model_sizes.json")

# Cache module-level pour read_preferences(), invalide au mtime (fix P1 #4
# audit 2026-07-21 : sur cle USB lente, ce fichier etait relu a chaque appel,
# soit 2x par requete /api/jarvis).
_preferences_cache: dict = {}
_preferences_mtime: float = 0.0


def _load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_model_sizes() -> dict:
    return _load_json(MODEL_SIZES_PATH)


def recommend_model(specs: dict) -> dict:
    sizes = load_model_sizes()
    if not sizes:
        return {"model": "qwen2.5", "fallback": True}

    ram_gb = specs.get("ram_gb", 0)
    vram_gb = specs.get("vram_gb", 0)
    cpu_only = specs.get("cpu_only", False)

    compatible = []
    for name, info in sizes.items():
        if info.get("embedding", False):
            continue
        if cpu_only and not info.get("cpu_only", False):
            continue
        if not cpu_only and info.get("cpu_only", False):
            continue
        # OOM guard: 20% headroom
        if ram_gb * 0.8 < info.get("ram_min_gb", 999):
            continue
        if not cpu_only and vram_gb < info.get("vram_min_gb", 0):
            continue
        compatible.append((name, info))

    if not compatible:
        return {"model": "qwen2.5", "fallback": True}

    compatible.sort(key=lambda x: x[1].get("ram_min_gb", 0), reverse=True)
    return {"model": compatible[0][0], "fallback": False}


def _warn(log_service, message: str) -> None:
    if log_service:
        log_service.log("WARN", message)


def read_preferences() -> dict:
    """Charge les préférences utilisateur depuis le fichier JSON config.

    Cache module-level avec invalidation au mtime pour éviter une relecture
    disque à chaque appel (2x par requête /api/jarvis, coûteux sur clé USB
    lente). Retourne un dict vide si le fichier est absent ou corrompu.
    """
    global _preferences_mtime

    try:
        current_mtime = os.path.getmtime(PREFERENCES_PATH)
    except OSError:
        return {}

    if current_mtime != _preferences_mtime:
        _preferences_cache.clear()
        _preferences_cache.update(_load_json(PREFERENCES_PATH))
        _preferences_mtime = current_mtime

    return _preferences_cache


def fallback_models() -> dict:
    """Correspondance agent -> modèle par défaut quand aucune préférence n'est définie."""
    return {
        "cyber":    "ornith-1.0-9b",
        "dev":      "deepseek-coder-v2-lite-instruct",
        "network":  "ornith-1.0-9b",
        "hardware": "qwen2.5",
        VISION_KEY: "llama3.2-vision",
    }


def _first_available(inference, models: Sequence[str]) -> str | None:
    """Parcourt une séquence de modèles et retourne le premier disponible
    (tag Ollama reel, pas le nom court de config)."""
    for model in models:
        resolved = inference.resolve_model(model)
        if resolved:
            return resolved
    return None


def select_vision_model(inference) -> str | None:
    """Sélectionne le premier modèle vision disponible (tag reel)."""
    return _first_available(inference, VISION_MODELS)


def select_model(agent_key: str, inference, log_service=None) -> str:
    """Sélectionne le meilleur modèle pour un agent donné.

    Stratégie :
      0. Court-circuit si agent vision (modèle vision disponible ou "auto")
      1. Préférences utilisateur
      2. Carte de fallback
      3. Premier modèle disponible sur le backend (hors modèles vision)
       4. Valeur "" (vide) si rien trouvé — le appelant doit traiter
          l'absence de modele (erreur "Aucun modele disponible")

    Renvoie un tag Ollama reel resolu, ou "" si aucun modele n'est disponible.
    """
    if agent_key == VISION_KEY:
        return select_vision_model(inference) or ""

    prefs = read_preferences()
    model_map = prefs.get("model_map", fallback_models())

    generic_values = [m for m in model_map.values() if m not in set(VISION_MODELS)]
    candidates = [model_map.get(agent_key)] + generic_values
    seen = set()
    for model in candidates:
        if model and model not in seen:
            seen.add(model)
            resolved = inference.resolve_model(model)
            if resolved:
                return resolved

    fallback = inference.first_available()
    if fallback:
        _warn(log_service, f"Fallback vers '{fallback}'")
        return fallback

    _warn(log_service, f"Aucun modele pour {agent_key}")
    return ""
