"""MetricsService — Métriques d'usage (uptime, requêtes, pipelines, erreurs).

Les compteurs sont bufferisés en mémoire : aucun écriture disque par
incrément (``write_json_atomic`` + ``os.fsync`` coûteux sur clef USB et
usure du support). Persistance :
- périodique (piggyback : à chaque incrément/lecture, si l'intervalle de
  60 s est écoulé) — pas de thread dédié ;
- immédiate via ``flush()`` public, déclenché à l'arrêt propre par
  ``controllers/warmup.py::_shutdown_sequence``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

from config.constants import MEMORY_DIR
from ports import MetricsPort
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.metrics")

# Fichier de persistance des métriques (conservées entre redémarrages)
METRICS_PATH = os.path.join(MEMORY_DIR, "metrics.json")
_lock = threading.RLock()

# Intervalle de persistance périodique (piggyback, pas de thread)
FLUSH_INTERVAL_SECONDS = 60.0

# psutil est optionnel : import défensif pour ne pas casser l'install portable
try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    _logger.debug("psutil indisponible, métriques CPU/mémoire désactivées.")
    psutil = None
    _PSUTIL_AVAILABLE = False
except Exception as e:
    _logger.debug("Erreur inattendue lors de l'import de psutil : %s", e)
    psutil = None
    _PSUTIL_AVAILABLE = False


def get_resource_usage() -> dict[str, Any]:
    """Renvoie l'usage mémoire/CPU du processus courant.

    Tente d'utiliser psutil ; sinon renvoie des valeurs nulles avec un flag explicite.
    """
    if _PSUTIL_AVAILABLE and psutil is not None:
        try:
            proc = psutil.Process(os.getpid())
            rss_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
            # interval=None compare à la dernière appel, peut être 0.0 au premier appel
            cpu_percent = psutil.cpu_percent(interval=None)
            return {
                "memory_rss_mb": rss_mb,
                "cpu_percent": cpu_percent,
                "psutil_available": True,
            }
        except Exception as e:
            _logger.debug("Échec de la collecte des métriques système : %s", e)

    return {
        "memory_rss_mb": None,
        "cpu_percent": None,
        "psutil_available": False,
    }


class MetricsService(MetricsPort):
    """Service de suivi des métriques d'usage et de performance."""

    def __init__(
        self,
        flush_interval: float = FLUSH_INTERVAL_SECONDS,
        now: Callable[[], float] = time.time,
    ) -> None:
        """Charge les métriques depuis le disque, initialise les compteurs à zéro si nouveau fichier.

        ``now`` est injectable pour les tests (horloge simulée, zéro sleep).
        """
        os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
        self._flush_interval = flush_interval
        self._now = now
        self._last_flush_ts = now()
        self._data = self._load()

        # Initialisation défensive des valeurs par défaut
        self._data.setdefault("uptime", time.time())
        self._data.setdefault("requests", 0)
        self._data.setdefault("pipeline_runs", 0)
        self._data.setdefault("errors", 0)
        self._data.setdefault("by_endpoint", {})

    def _load(self) -> dict[str, Any]:
        """Charge les métriques depuis metrics.json."""
        try:
            with open(METRICS_PATH, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as e:
            _logger.debug("metrics.json illisible ou absent, réinitialisation : %s", e)
            return {}

    def _save(self) -> None:
        """Persiste les métriques sur disque de manière atomique."""
        with _lock:
            write_json_atomic(METRICS_PATH, self._data)

    def flush(self) -> None:
        """Persiste immédiatement le buffer mémoire (arrêt propre, P10)."""
        with _lock:
            self._save()
            self._last_flush_ts = self._now()

    def _maybe_flush(self) -> None:
        """Persiste si l'intervalle est écoulé (piggyback, pas de thread dédié)."""
        if self._now() - self._last_flush_ts >= self._flush_interval:
            self.flush()

    def incr_requests(self, endpoint: str = "/api/jarvis") -> None:
        """Incrémente le compteur global de requêtes et le compteur par endpoint."""
        with _lock:
            self._data["requests"] += 1
            by_endpoint = self._data.setdefault("by_endpoint", {})
            by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + 1
            self._maybe_flush()

    def incr_pipeline_run(self) -> None:
        """Incrémente le compteur d'exécutions de pipelines."""
        with _lock:
            self._data["pipeline_runs"] += 1
            self._maybe_flush()

    def incr_errors(self) -> None:
        """Incrémente le compteur d'erreurs."""
        with _lock:
            self._data["errors"] += 1
            self._maybe_flush()

    def get_metrics(self) -> dict[str, Any]:
        """Retourne toutes les métriques agrégées avec l'uptime formaté."""
        with _lock:
            self._maybe_flush()
            start_time = self._data.get("uptime", time.time())
            uptime = round(time.time() - start_time, 1)

            result = {
                "uptime_seconds": uptime,
                "uptime_human": self._format_uptime(uptime),
                "requests": self._data.get("requests", 0),
                "pipeline_runs": self._data.get("pipeline_runs", 0),
                "errors": self._data.get("errors", 0),
                "by_endpoint": dict(self._data.get("by_endpoint", {})),  # Copie défensive
            }

        # Métriques système (hors lock car ne modifie pas l'état partagé)
        result.update(get_resource_usage())
        return result

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Convertit des secondes en format lisible 'Xh Ym Zs'."""
        h, r = divmod(int(seconds), 3600)
        m, s = divmod(r, 60)
        return f"{h}h {m}m {s}s"


__all__ = ["MetricsService", "get_resource_usage"]
