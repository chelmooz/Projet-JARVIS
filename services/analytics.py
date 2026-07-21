"""Service analytics — Statistiques d'usage des requêtes (agents, modèles, latence).

Responsabilité unique (SRP) :
- Persister et agréger les métriques d'usage (requêtes, latence, succès).
- Garantir la thread-safety des accès concurrents (RLock).
- Assurer la migration rétrocompatible des anciens formats de données.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from typing import Any

from config.constants import MAX_QUERIES, MEMORY_DIR
from ports import AnalyticsPort
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.analytics")

# Fichier de persistance des statistiques
ANALYTICS_PATH = os.path.join(MEMORY_DIR, "analytics.json")
_lock = threading.RLock()


class AnalyticsService(AnalyticsPort):
    """Service de statistiques d'usage (thread-safe)."""

    def __init__(self, path: str | None = None) -> None:
        """Charge les stats depuis le disque.
        
        Args:
            path: Chemin personnalisé pour les tests (défaut: ANALYTICS_PATH).
        """
        self._path = path or ANALYTICS_PATH
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        """Charge les données analytics depuis le fichier JSON."""
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            if "queries" not in data:
                data = self._migrate(data)
            return data
        except (OSError, json.JSONDecodeError) as e:
            _logger.debug("analytics.json illisible ou absent, stats initialisées à vide : %s", e)
            return {"queries": [], "agents": {}, "models": {}}

    @staticmethod
    def _migrate(old: dict[str, Any]) -> dict[str, Any]:
        """Migre l'ancien format (by_agent/by_model) vers le nouveau format (queries/agents/models)."""
        return {
            "queries": [],
            "agents": old.get("by_agent", {}),
            "models": old.get("by_model", {}),
        }

    def _save(self) -> None:
        """Persiste les données sur disque (atomique)."""
        # Note : _save est appelé depuis des contextes déjà verrouillés (RLock supporte la réentrance).
        write_json_atomic(self._path, self._data)

    def track_query(
        self,
        agent: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """Enregistre une requête dans les stats (agent, modèle, métriques)."""
        with _lock:
            queries = self._data.setdefault("queries", [])
            queries.append({
                "agent": agent,
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
                "success": success,
                "ts": time.time(),
            })
            
            # Troncature si dépassement de la borne MAX_QUERIES
            if len(queries) > MAX_QUERIES:
                self._data["queries"] = queries[-MAX_QUERIES:]
            
            # Mise à jour des compteurs agrégés
            agents = self._data.setdefault("agents", {})
            agents[agent] = agents.get(agent, 0) + 1
            
            models = self._data.setdefault("models", {})
            models[model] = models.get(model, 0) + 1
            
            self._save()

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques globales (total, taux succès, latence moyenne, répartition)."""
        with _lock:
            # Copie défensive pour ne pas exposer la référence interne mutable
            # et réduire la durée du verrou (calculs lourds sortis du bloc critique).
            q = list(self._data.get("queries", []))
            agents = dict(self._data.get("agents", {}))
            models = dict(self._data.get("models", {}))

        total = len(q)
        success = sum(1 for x in q if x.get("success"))
        avg_latency = round(sum(x.get("latency_ms", 0) for x in q) / total, 1) if total else 0.0
        
        # Heuristique : l'agent "vectorize" correspond aux conversations ingestées
        total_conversations = sum(1 for x in q if x.get("agent") == "vectorize")

        return {
            "total_queries": total,
            "total_conversations": total_conversations,
            "success_rate": round(success / total * 100, 1) if total else 0.0,
            "avg_latency_ms": avg_latency,
            "queries": q,
            "agents": agents,
            "models": models,
        }

    def get_most_used(self) -> dict[str, Any]:
        """Retourne l'agent et le modèle les plus utilisés."""
        with _lock:
            agents = Counter(self._data.get("agents", {}))
            models = Counter(self._data.get("models", {}))

        return {
            "top_agent": agents.most_common(1)[0] if agents else None,
            "top_model": models.most_common(1)[0] if models else None,
        }


__all__ = ["AnalyticsService"]
