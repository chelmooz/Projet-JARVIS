"""DimensionManager — cohérence de dimension d'embedding et migration.

Responsabilité unique (SRP) : détecter un changement de dimension d'embedding
(stockée vs attendue) et déclencher un re-index paresseux ou un reset propre.
"""
from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("jarvis.vector")

MIGRATION_OK = "ok"
MIGRATION_REINDEXED = "reindexed"
MIGRATION_RESET = "reset"


class DimensionManager:
    """Garantit la cohérence dimension/embarquement du store vectoriel."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def ensure_dimension(self, expected_dim: int, expected_model: str) -> str:
        """Retourne le statut de migration (OK / REINDEXED / RESET)."""
        stored_dim = self._data.get("embedding_dim")
        stored_model = self._data.get("embedding_model")
        
        if stored_dim is None:
            self._init_dimension(expected_dim, expected_model)
            return MIGRATION_OK
            
        if stored_dim == expected_dim and stored_model == expected_model:
            return MIGRATION_OK
            
        return self._migrate(stored_dim, stored_model, expected_dim, expected_model)

    def _init_dimension(self, expected_dim: int, expected_model: str) -> None:
        """Initialise la dimension et le modèle d'embedding par défaut."""
        self._data["embedding_dim"] = expected_dim
        self._data["embedding_model"] = expected_model

    def _migrate(
        self,
        stored_dim: int | None,
        stored_model: str | None,
        expected_dim: int,
        expected_model: str,
    ) -> str:
        """Gère la migration si la dimension ou le modèle a changé."""
        _logger.warning(
            "MIGRATION dimension embedding : stockée=%s, attendue=%s (modèle %s -> %s)",
            stored_dim, expected_dim, stored_model, expected_model,
        )
        documents = self._data.get("documents", [])
        textes_disponibles = [d for d in documents if d.get("text")]
        
        if textes_disponibles:
            return self._schedule_reindex(documents, expected_dim, expected_model, len(textes_disponibles))
        return self._reset_index(expected_dim, expected_model)

    def _schedule_reindex(
        self,
        documents: list[dict[str, Any]],
        expected_dim: int,
        expected_model: str,
        n_texts: int,
    ) -> str:
        """Re-index paresseux : texte conservé, embeddings invalidés."""
        for doc in documents:
            doc["embedding"] = None
            
        self._data["embedding_dim"] = expected_dim
        self._data["embedding_model"] = expected_model
        
        _logger.info(
            "Re-index planifié (paresseux) de %s document(s) pour la nouvelle dimension %s",
            n_texts, expected_dim,
        )
        return MIGRATION_REINDEXED

    def _reset_index(self, expected_dim: int, expected_model: str) -> str:
        """Reset propre : aucun texte à re-indexer (mute le dict existant)."""
        self._data.clear()
        self._data.update({
            "documents": [],
            "embeddings": [],
            "embedding_dim": expected_dim,
            "embedding_model": expected_model,
        })
        _logger.warning(
            "Reset propre de l'index vectoriel : aucun texte à ré-indexer. "
            "Ré-indexez vos sources pour repeupler l'index (dimension %s).",
            expected_dim,
        )
        return MIGRATION_RESET


__all__ = [
    "MIGRATION_OK",
    "MIGRATION_REINDEXED",
    "MIGRATION_RESET",
    "DimensionManager",
]
