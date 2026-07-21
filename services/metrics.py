"""MetricsService — Métriques d'usage (uptime, requêtes, pipelines, erreurs).

NOTE DevOps / Performance :
L'implémentation actuelle persiste sur disque à chaque incrémentation (via write_json_atomic).
Sur un support de type clef USB, les appels répétés à os.fsync() peuvent dégrader les 
performances et la durée de vie du support. 
Cible d'évolution : Bufferiser les compteurs en mémoire et persister uniquement 
périodiquement (ex: toutes les 60s) ou lors du graceful shutdown.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

from config.constants import MEMORY_DIR
from ports import MetricsPort
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.metrics")

# Fichier de persistance des métriques (conservées entre redémarrages)
METRICS_PATH = os.path.join(MEMORY_DIR, "metrics.json")
_lock = threading.RLock()

# psutil est optionnel : import défensif pour ne pas casser l'install portable
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _logger.debug("psutil indisponible, métriques CPU/mémoire désactivées.")
    psutil = None  # type: ignore
    _PSUTIL_AVAILABLE = False
except Exception as e:
    _logger.debug("Erreur inattendue lors de l'import de psutil : %s", e)
    psutil = None  # type: ignore
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

    def __init__(self) -> None:
        """Charge les métriques depuis le disque, initialise les compteurs à zéro si nouveau fichier."""
        os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
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

    def incr_requests(self, endpoint: str = "/api/jarvis") -> None:
        """Incrémente le compteur global de requêtes et le compteur par endpoint."""
        with _lock:
            self._data["requests"] += 1
            by_endpoint = self._data.setdefault("by_endpoint", {})
            by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + 1
            # NOTE : Appel coûteux en I/O sur chaque requête (voir note de module)
            write_json_atomic(METRICS_PATH, self._data)

    def incr_pipeline_run(self) -> None:
        """Incrémente le compteur d'exécutions de pipelines."""
        with _lock:
            self._data["pipeline_runs"] += 1
            write_json_atomic(METRICS_PATH, self._data)

    def incr_errors(self) -> None:
        """Incrémente le compteur d'erreurs."""
        with _lock:
            self._data["errors"] += 1
            write_json_atomic(METRICS_PATH, self._data)

    def get_metrics(self) -> dict[str, Any]:
        """Retourne toutes les métriques agrégées avec l'uptime formaté."""
        with _lock:
            start_time = self._data.get("uptime", time.time())
            uptime = round(time.time() - start_time, 1)
            
            result = {
                "uptime_seconds": uptime,
                "uptime_human": self._format_uptime(uptime),
                "requests": self._data.get("requests", 0),
                "pipeline_runs": self._data.get("pipeline_runs", 0),
                "errors": self._data.get("errors", 0),
                "by_endpoint": dict(self._data.get("by_endpoint", {})), # Copie défensive
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
