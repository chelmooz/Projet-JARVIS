#!/usr/bin/env python3
"""Verrou : flush des métriques garanti à l'arrêt propre (audit P10).

RED : le buffer mémoire ne serait jamais vidé si l'intervalle n'est pas
écoulé au shutdown. Le point d'arrêt centralisé (``_shutdown_sequence``,
controllers/warmup.py) doit déclencher ``metrics.flush()``.
"""

import asyncio
import unittest

from controllers.warmup import _shutdown_sequence


class FakeMetrics:
    def __init__(self) -> None:
        self.flush_called = False

    def flush(self) -> None:
        self.flush_called = True


class FakeContext:
    def __init__(self) -> None:
        self._warmup_tasks: list[asyncio.Task[None]] = []
        self.metrics = FakeMetrics()


class TestMetricsFlushOnShutdown(unittest.TestCase):
    """TEST: l'arrêt propre vide le buffer des métriques."""

    def test_shutdown_sequence_flushes_metrics(self) -> None:
        """RED : metrics.flush() doit être appelé même sans intervalle écoulé."""
        ctx = FakeContext()
        asyncio.run(_shutdown_sequence(ctx))
        self.assertTrue(
            ctx.metrics.flush_called,
            "_shutdown_sequence doit persister les métriques bufferisées",
        )


if __name__ == "__main__":
    unittest.main()
