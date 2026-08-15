#!/usr/bin/env python3
"""Verrou de comportement : metrics bufferisées (audit P10).

RED : chaque incrément persistait sur disque via ``write_json_atomic``
(+ ``os.fsync``) — coûteux sur clef USB et usure du support (NOTE de module).
Contrat attendu :
1. incrémenter N fois n'écrit RIEN sur disque (buffer mémoire) ;
2. après expiration de l'intervalle (horloge injectée, zéro sleep), l'écriture
   survient une fois (flush périodique piggyback) ;
3. ``flush()`` explicite persiste immédiatement.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.metrics import MetricsService


class TestMetricsBufferedFlush(unittest.TestCase):
    """TEST: incréments en mémoire, écriture différée (intervalle ou flush)."""

    def setUp(self) -> None:
        self._tmp = Path(tempfile.mkdtemp())

    @patch("services.metrics.write_json_atomic")
    def test_increments_do_not_write_disk(self, save) -> None:
        """RED : 10 incréments → zéro écriture disque."""
        with patch("services.metrics.METRICS_PATH", str(self._tmp / "metrics.json")):
            svc = MetricsService()
            for _ in range(10):
                svc.incr_requests("/api/jarvis")
            svc.incr_pipeline_run()
            svc.incr_errors()
        save.assert_not_called()

    @patch("services.metrics.write_json_atomic")
    def test_flush_after_interval_with_injected_clock(self, save) -> None:
        """RED : intervalle écoulé → une seule écriture (horloge injectée)."""
        ticks = iter([100.0, 100.0, 161.0, 161.0])
        with patch("services.metrics.METRICS_PATH", str(self._tmp / "metrics.json")):
            svc = MetricsService(now=lambda: next(ticks))
            svc.incr_requests("/api/jarvis")  # t=100, intervalle non écoulé
            save.assert_not_called()
            svc.incr_requests("/api/jarvis")  # t=161, 61s > 60s → flush
        save.assert_called_once()

    @patch("services.metrics.write_json_atomic")
    def test_explicit_flush_persists_immediately(self, save) -> None:
        """RED : flush() explicite → écriture immédiate."""
        with patch("services.metrics.METRICS_PATH", str(self._tmp / "metrics.json")):
            svc = MetricsService()
            svc.incr_requests("/api/jarvis")
            save.assert_not_called()
            svc.flush()
        save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
