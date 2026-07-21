"""Selecteur de modèles — Choisit le meilleur modèle disponible pour un agent."""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Sequence
from typing import Any

from config.constants import PROJECT_DIR

_logger = logging.getLogger("jarvis.selector")

# --- Constantes de configuration ---
PREFERENCES_PATH = os.path.join(PROJECT_DIR, "config", "model_preferences.json")
MODEL_SIZES_PATH = os.path.join(PROJECT_DIR, "config", "model_sizes.json")

VISION_KEY = "vision"
VISION_MODELS = ["llama3.2-vision"]
DEFAULT_FALLBACK_MODEL = "qwen2.5"
RAM_HEADROOM_RATIO = 0.8  # 20% de marge de sécurité pour éviter les OOM


class _PreferencesCache:
    """Cache thread-safe pour les préférences utilisateur avec invalidation au mtime.
    
    Remplace les variables globales mutables par un état encapsulé et testable.
    """
    
    def __init__(self, path: str) -> None:
        self._path = path
        self._cache: dict[str, Any] = {}
        self._mtime: float = 0.0
        self._lock = threading.Lock()

    def get(self) -> dict[str, Any]:
        """Retourne les préférences actuelles, en rechargeant si le fichier a changé."""
        try:
            current_mtime = os.path.getmtime(self._path)
        except OSError:
            return {}

        with self._lock:
            if current_mtime != self._mtime:
                self._cache.clear()
                self._cache.update(self._load_json())
                self._mtime = current_mtime
            # Retourne une copie pour éviter la mutation externe du cache
            return self._cache.copy()

    def _load_json(self) -> dict[str, Any]:
        """Charge le fichier JSON de préférences."""
        try:
            with open(self._path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            _logger.warning("Fichier de préférences corrompu (%s): %s", self._path, e)
            return {}


# Instance unique du cache (remplace les globals mutables)
_prefs_cache = _PreferencesCache(PREFERENCES_PATH)


def _load_json(path: str) -> dict[str, Any]:
    """Charge un fichier JSON de manière sécurisée."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        _logger.warning("Fichier JSON corrompu (%s): %s", path, e)
        return {}


def load_model_sizes() -> dict[str, Any]:
    """Charge la configuration des tailles de modèles."""
    return _load_json(MODEL_SIZES_PATH)


def recommend_model(specs: dict[str, Any]) -> dict[str, Any]:
    """Recommande un modèle basé sur les spécifications matérielles.
    
    Args:
        specs: Dictionnaire contenant 'ram_gb', 'vram_gb', 'cpu_only'.
        
    Returns:
        Dictionnaire avec 'model' et 'fallback'.
    """
    sizes = load_model_sizes()
    if not sizes:
        return {"model": DEFAULT_FALLBACK_MODEL, "fallback": True}

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
        
        # Garde-fou OOM avec marge de sécurité
        if ram_gb * RAM_HEADROOM_RATIO < info.get("ram_min_gb", 999):
            continue
        if not cpu_only and vram_gb < info.get("vram_min_gb", 0):
            continue
            
        compatible.append((name, info))

    if not compatible:
        return {"model": DEFAULT_FALLBACK_MODEL, "fallback": True}

    # Trie par consommation RAM décroissante (priorise les modèles plus lourds si la RAM le permet)
    compatible.sort(key=lambda x: x[1].get("ram_min_gb", 0), reverse=True)
    return {"model": compatible[0][0], "fallback": False}


def read_preferences() -> dict[str, Any]:
    """Charge les préférences utilisateur (avec cache thread-safe)."""
    return _prefs_cache.get()


def fallback_models() -> dict[str, str]:
    """Correspondance agent -> modèle par défaut."""
    return {
        "cyber": "ornith-1.0-9b",
        "dev": "deepseek-coder-v2-lite-instruct",
        "network": "ornith-1.0-9b",
        "hardware": DEFAULT_FALLBACK_MODEL,
        VISION_KEY: VISION_MODELS[0],
    }


def _first_available(inference: Any, models: Sequence[str]) -> str | None:
    """Retourne le premier modèle disponible dans la liste."""
    for model in models:
        resolved = inference.resolve_model(model)
        if resolved:
            return resolved
    return None


def select_vision_model(inference: Any) -> str | None:
    """Sélectionne le premier modèle vision disponible."""
    return _first_available(inference, VISION_MODELS)


def select_model(agent_key: str, inference: Any, log_service: Any | None = None) -> str:
    """Sélectionne le meilleur modèle pour un agent donné.
    
    Stratégie :
      1. Court-circuit vision
      2. Préférences utilisateur
      3. Fallback par agent
      4. Premier modèle générique disponible
      5. Chaîne vide si aucun modèle (l'appelant doit gérer l'erreur)
      
    Args:
        agent_key: Clé de l'agent (ex: 'cyber', 'dev', 'vision').
        inference: Service d'inférence (doit implémenter resolve_model/first_available).
        log_service: Service de log optionnel pour les avertissements.
        
    Returns:
        Nom du modèle sélectionné, ou chaîne vide si aucun modèle n'est disponible.
    """
    if agent_key == VISION_KEY:
        return select_vision_model(inference) or ""

    prefs = read_preferences()
    model_map = prefs.get("model_map", fallback_models())

    # Construit la liste des candidats : modèle spécifique à l'agent + modèles génériques
    generic_values = [m for m in model_map.values() if m not in VISION_MODELS]
    candidates = [model_map.get(agent_key)] + generic_values
    
    seen = set()
    for model in candidates:
        if model and model not in seen:
            seen.add(model)
            resolved = inference.resolve_model(model)
            if resolved:
                return resolved

    # Ultime fallback : premier modèle disponible sur le backend
    fallback = inference.first_available()
    if fallback:
        if log_service:
            log_service.log("WARN", f"Fallback vers '{fallback}'")
        return fallback

    if log_service:
        log_service.log("WARN", f"Aucun modèle disponible pour l'agent '{agent_key}'")
    return ""


__all__ = [
    "recommend_model",
    "read_preferences",
    "fallback_models",
    "select_vision_model",
    "select_model",
]
