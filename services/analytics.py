"""Service analytics — Statistiques d'usage des requêtes (agents, modèles, latence)."""
import json
import logging
import os
import threading
import time
from collections import Counter

from config.constants import MAX_QUERIES, MEMORY_DIR
from ports import AnalyticsPort as AnalyticsPortABC
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.analytics")

# Fichier de persistance des statistiques
ANALYTICS_PATH = os.path.join(MEMORY_DIR, "analytics.json")
_lock = threading.RLock()


class AnalyticsService(AnalyticsPortABC):
    """AnalyticsService."""

    def __init__(self, path: str | None = None):
        """Charge les stats depuis le disque. Accepte un path personnalisé pour les tests."""
        self._path = path or ANALYTICS_PATH
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        """Charge les données analytics depuis le fichier JSON."""
        try:
            with open(self._path) as f:
                data = json.load(f)
            if "queries" not in data:
                data = self._migrate(data)
            return data
        except Exception as e:
            _logger.debug("analytics.json illisible/absent, stats vides: %s", e)
            return {"queries": [], "agents": {}, "models": {}}

    @staticmethod
    def _migrate(old: dict) -> dict:
        """Migre l'ancien format (by_agent/by_model) vers le nouveau format (queries/agents/models)."""
        return {"queries": [], "agents": old.get("by_agent", {}), "models": old.get("by_model", {})}

    def _save(self):
        with _lock:
            write_json_atomic(self._path, self._data)

    def track_query(self, agent: str, model: str, tokens_in: int = 0,
                    tokens_out: int = 0, latency_ms: float = 0, success: bool = True):
        """Enregistre une requête dans les stats (agent, modèle, métriques)."""
        with _lock:
            self._data.setdefault("queries", []).append({
                "agent": agent, "model": model,
                "tokens_in": tokens_in, "tokens_out": tokens_out,
                "latency_ms": latency_ms, "success": success,
                "ts": time.time(),
            })
            self._data.setdefault("agents", {}).setdefault(agent, 0)
            self._data["agents"][agent] += 1
            self._data.setdefault("models", {}).setdefault(model, 0)
            self._data["models"][model] += 1
            if len(self._data.get("queries", [])) > MAX_QUERIES:
                self._data["queries"] = self._data["queries"][-MAX_QUERIES:]
            self._save()

    def get_stats(self) -> dict:
        """Retourne les statistiques globales (total, taux succès, latence moyenne, répartition)."""
        with _lock:
            q = self._data.get("queries", []).copy()
            total = len(q)
            success = sum(1 for x in q if x.get("success"))
            avg_latency = round(sum(x.get("latency_ms", 0) for x in q) / total, 1) if total else 0
            total_conversations = sum(1 for x in q if x.get("agent") == "vectorize")
            return {
                "total_queries": total,
                "total_conversations": total_conversations,
                "success_rate": round(success / total * 100, 1) if total else 0,
                "avg_latency_ms": avg_latency,
                "queries": q,
                "agents": self._data.get("agents", {}),
                "models": self._data.get("models", {}),
            }

    def get_most_used(self) -> dict:
        """Retourne l'agent et le modèle les plus utilisés."""
        with _lock:
            agents = Counter(self._data.get("agents", {}))
            models = Counter(self._data.get("models", {}))
        return {
            "top_agent": agents.most_common(1)[0] if agents else None,
            "top_model": models.most_common(1)[0] if models else None,
        }
