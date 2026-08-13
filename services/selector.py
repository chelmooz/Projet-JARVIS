"""Selecteur de modèles — Choisit le meilleur modèle disponible pour un agent."""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

from config.constants import PROJECT_DIR

_logger = logging.getLogger("jarvis.selector")

# --- Constantes de configuration ---
PREFERENCES_PATH = os.path.join(PROJECT_DIR, "config", "model_preferences.json")
MODEL_SIZES_PATH = os.path.join(PROJECT_DIR, "config", "model_sizes.json")

VISION_KEY = "vision"
# RapidOCR (services/ocr.py) gère désormais l'extraction de texte depuis une
# image : ce n'est plus un modèle Ollama, donc plus besoin de résoudre/pull un
# modèle vision. La sentinelle ci-dessous sert uniquement à la télémétrie
# (logs, métriques) — elle n'est jamais passée à Ollama.
VISION_OCR_SENTINEL = "rapidocr"
DEFAULT_FALLBACK_MODEL = "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"
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
                return dict(json.load(f))
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
            return dict(json.load(f))
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
        "cyber": "hf.co/GGUF-A-Lot/DeepHat-V1-7B-GGUF:Q4_K_M",
        "dev": "hf.co/bartowski/ibm-granite_granite-4.1-8b-GGUF:Q4_K_M",
        "network": "hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF:Q8_0",
        "hardware": DEFAULT_FALLBACK_MODEL,
        VISION_KEY: VISION_OCR_SENTINEL,
    }


def select_vision_model(inference: Any) -> str | None:
    """Renvoie la sentinelle RapidOCR (jamais ``None``).

    Historique : cherchait auparavant un modèle Ollama vision (``moondream``)
    via ``inference.resolve_model()``. Ce modèle n'est plus installé/assigné,
    ce qui faisait échouer silencieusement toute image droppée dans le chat
    (``select_model("vision", ...)`` renvoyait ``""``). RapidOCR ne dépendant
    pas d'Ollama, cette fonction ne peut plus échouer faute de modèle absent.
    Le paramètre ``inference`` est conservé pour compatibilité de signature
    (appelants existants : ``services/orchestrator.py``, ``controllers/di.py``).
    """
    del inference  # non utilisé : RapidOCR ne passe pas par Ollama
    return VISION_OCR_SENTINEL


def select_vision_analysis_model(inference: Any) -> str:
    """Modèle texte utilisé pour analyser le texte extrait par l'OCR.

    RapidOCR ne fait qu'extraire du texte (pas d'analyse). Le texte brut est
    ensuite confié à un LLM texte (généralement ``DEFAULT_FALLBACK_MODEL`` =
    ``Qwen2.5-7B``) qui répond à la consigne de l'utilisateur — recréant le
    comportement qu'avait ``moondream`` en un seul modèle multimodal, mais en
    deux étapes découplées.

    Args:
        inference: Service d'inférence (pour résoudre le tag Ollama réel).

    Returns:
        Nom du modèle résolu, ou ``DEFAULT_FALLBACK_MODEL`` si indéterminable.
    """
    if inference is not None:
        resolved = inference.resolve_model(DEFAULT_FALLBACK_MODEL)
        if resolved:
            return str(resolved)
    return DEFAULT_FALLBACK_MODEL


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
    generic_values = [m for m in model_map.values() if m != VISION_OCR_SENTINEL]
    candidates = [model_map.get(agent_key)] + generic_values

    seen = set()
    for model in candidates:
        if model and model not in seen:
            seen.add(model)
            resolved = inference.resolve_model(model)
            if resolved:
                return str(resolved)

    # Ultime fallback : premier modèle disponible sur le backend
    fallback = inference.first_available()
    if fallback:
        if log_service:
            log_service.log("WARN", f"Fallback vers '{fallback}'")
        return str(fallback)

    if log_service:
        log_service.log("WARN", f"Aucun modèle disponible pour l'agent '{agent_key}'")
    return ""


__all__ = [
    "recommend_model",
    "read_preferences",
    "fallback_models",
    "select_vision_model",
    "select_vision_analysis_model",
    "select_model",
]
