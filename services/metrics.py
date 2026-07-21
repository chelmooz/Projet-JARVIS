"""MetricsService — Métriques d'usage (uptime, requêtes, pipelines, erreurs)."""
import json
import logging
import os
import threading
import time

from config.constants import MEMORY_DIR
from ports import MetricsPort as MetricsPortABC
from services.file_utils import write_json_atomic

_logger = logging.getLogger("jarvis.metrics")

# Fichier de persistance des métriques (conservées entre redémarrages)
METRICS_PATH = os.path.join(MEMORY_DIR, "metrics.json")
_lock = threading.RLock()

# psutil est optionnel : import défensif pour ne pas casser l'install portable
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except Exception as e:
    _logger.debug("psutil indisponible, metriques CPU/memoire desactivees: %s", e)
    psutil = None
    _PSUTIL_AVAILABLE = False


def get_resource_usage() -> dict:
    """Renvoie l'usage mémoire/CPU du process courant.

    Tente psutil ; sinon renvoie None avec psutil_available=False.
    """
    if _PSUTIL_AVAILABLE:
        proc = psutil.Process(os.getpid())
        rss_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
        cpu_percent = psutil.cpu_percent(interval=None)
        return {
            "memory_rss_mb": rss_mb,
            "cpu_percent": cpu_percent,
            "psutil_available": True,
        }
    return {
        "memory_rss_mb": None,
        "cpu_percent": None,
        "psutil_available": False,
    }


class MetricsService(MetricsPortABC):
    """MetricsService."""

    def __init__(self):
        """Charge les métriques depuis le disque, initialise les compteurs à zéro si nouveau fichier."""
        os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
        self._data = self._load()
        self._data.setdefault("uptime", time.time())
        self._data.setdefault("requests", 0)
        self._data.setdefault("pipeline_runs", 0)
        self._data.setdefault("errors", 0)
        self._data.setdefault("by_endpoint", {})

    def _load(self) -> dict:
        """Charge les métriques depuis metrics.json."""
        with _lock:
            try:
                with open(METRICS_PATH) as f:
                    return json.load(f)
            except Exception as e:
                _logger.debug("metrics.json illisible/absent, repart de zero: %s", e)
                return {}

    def _save(self):
        with _lock:
            write_json_atomic(METRICS_PATH, self._data)

    def incr_requests(self, endpoint: str = "/api/jarvis"):
        """Incrémente le compteur global de requêtes et le compteur par endpoint."""
        with _lock:
            self._data["requests"] += 1
            self._data.setdefault("by_endpoint", {}).setdefault(endpoint, 0)
            self._data["by_endpoint"][endpoint] += 1
            self._save()

    def incr_pipeline_run(self):
        """Incrémente le compteur d'exécutions de pipelines."""
        with _lock:
            self._data["pipeline_runs"] += 1
            self._save()

    def incr_errors(self):
        """Incrémente le compteur d'erreurs."""
        with _lock:
            self._data["errors"] += 1
            self._save()

    def get_metrics(self) -> dict:
        """Retourne toutes les métriques avec l'uptime formaté."""
        with _lock:
            uptime = round(time.time() - self._data.get("uptime", time.time()), 1)
            result = {
                "uptime_seconds": uptime,
                "uptime_human": self._format_uptime(uptime),
                "requests": self._data.get("requests", 0),
                "pipeline_runs": self._data.get("pipeline_runs", 0),
                "errors": self._data.get("errors", 0),
                "by_endpoint": self._data.get("by_endpoint", {}),
            }
            # Métriques mémoire/CPU (psutil optionnel)
            result.update(get_resource_usage())
            return result

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Convertit des secondes en format lisible 'Xh Ym Zs'."""
        h, r = divmod(int(seconds), 3600)
        m, s = divmod(r, 60)
        return f"{h}h {m}m {s}s"
