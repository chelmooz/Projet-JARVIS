"""Résolution de modèles Ollama — fonctions pures (match tolérant, tags HF-GGUF).

Extraites de ``OllamaAdapter`` (découpage Phase 20) : la logique de
matching et de sélection des modèles est indépendante du transport HTTP
et peut être testée isolément.
"""

from __future__ import annotations

from typing import Any


def repo_name(tag: str) -> str:
    """Extrait le nom de dépôt d'un tag Ollama (suffixe -gguf retiré).

    'hf.co/org/Repo-GGUF:Q4_K_M'     -> 'repo'
    'hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M' -> 'qwen2.5-7b-instruct'
    """
    name = tag.rsplit("/", 1)[-1].lower()
    return name.split(":", 1)[0].removesuffix("-gguf")


def matches(available: list[str], model: str) -> bool:
    """Match tolérant : nom exact OU base name == nom de repo du tag.

    Les modèles HF importés portent un tag de la forme
    'hf.co/<org>/<repo>-GGUF:Q4_K_M' ; on accepte donc qu'un nom court
    (ex: 'phi-4-mini-instruct-abliterated') matche 'repo-gguf'
    (sans le suffixe GGUF).
    """
    model = model.strip().lower()
    wanted = model.removesuffix("-gguf")
    for tag in available:
        if tag.lower() == model:
            return True
        if repo_name(tag) == wanted:
            return True
    return False


def resolve_tag(available: list[str], model: str) -> str | None:
    """Retourne le tag Ollama réel correspondant à un nom court de config.

    'qwen2.5' -> 'hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M'
    'phi-4-mini-instruct-abliterated' -> 'hf.co/Melvin56/...-GGUF:Q4_K_M'
    Renvoie None si aucun modèle ne matche.
    """
    if not model:
        return None
    if model in available:
        return model
    for tag in available:
        if matches([tag], model):
            return tag
    return None


def first_completion(models: list[dict[str, Any]], prefer_pure_text: bool = False) -> str | None:
    """Premier modèle ``completion`` de la liste, en excluant ``embedding``-only.

    ``prefer_pure_text`` : exclut aussi les modèles ``vision`` en première
    passe — un modèle vision branché sur le chat répond hors sujet ; il ne
    reste sélectionnable qu'en dernier recours.
    Un modèle sans champ ``capabilities`` (vieilles versions d'Ollama) est
    toujours éligible (comportement historique).
    """
    for entry in models:
        capabilities = entry.get("capabilities")
        if capabilities is None or "completion" in capabilities:
            if prefer_pure_text and capabilities is not None and "vision" in capabilities:
                continue
            return entry.get("name")
    return None
