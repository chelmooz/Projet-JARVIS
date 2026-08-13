"""Statistiques de l'index vectoriel — fonctions pures, sans état.

Extraites de ``VectorService`` (découpage Phase 20) : le calcul des
statistiques est délégué à des fonctions pures testables, la classe ne
garde que l'orchestration thread-safe.
"""

from __future__ import annotations

from typing import Any


def conversation_weights(documents: list[dict[str, Any]]) -> list[float]:
    """Poids des documents de source "conversation"."""
    return [
        d.get("metadata", {}).get("weight", 1.0)
        for d in documents
        if d.get("metadata", {}).get("source") == "conversation"
    ]


def weight_stats(conv_weights: list[float]) -> tuple[float, float]:
    """Statistiques de poids : (moyenne, ratio de poids faibles)."""
    if not conv_weights:
        return 0.0, 0.0
    mean = round(sum(conv_weights) / len(conv_weights), 3)
    low = round(sum(1 for w in conv_weights if w <= 0) / len(conv_weights), 3)
    return mean, low


def estimate_dedup(documents: list[dict[str, Any]]) -> int:
    """Estime le nombre de doublons potentiels (texte normalisé)."""
    text_counts: dict[str, int] = {}
    for d in documents:
        key = d["text"].strip().lower()
        text_counts[key] = text_counts.get(key, 0) + 1
    return sum(c - 1 for c in text_counts.values() if c > 1)


def cache_hit_rate(hits: int, misses: int) -> float:
    """Taux de hits du cache, en pourcentage (0.0 si aucun appel)."""
    total = hits + misses
    return round(hits / total * 100, 1) if total else 0.0
