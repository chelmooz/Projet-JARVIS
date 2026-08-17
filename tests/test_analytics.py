#!/usr/bin/env python3
"""Test that analytics stats work correctly."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import pytest

import services.analytics as analytics_module
from services.analytics import AnalyticsService

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAnalyticsStats(unittest.TestCase):
    """TEST: Analytics stats are correct after refactoring."""

    def test_analytics_stats_basic(self):
        """GREEN: Analytics stats return correct structure without total_conversations."""
        analytics = AnalyticsService()
        stats = analytics.get_stats()
        # Vérifier que la structure est correcte (total_conversations retiré)
        self.assertIn("total_queries", stats)
        self.assertIn("success_rate", stats)
        self.assertIn("avg_latency_ms", stats)
        self.assertIn("agents", stats)
        self.assertIn("models", stats)
        self.assertNotIn("total_conversations", stats)


def test_analytics_no_queries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GREEN: Sans requêtes, les stats sont vides/zeros (version isolée MT-KB-L2l).

    Le test historique lisait ``memory/analytics.json`` de production → échouait dès
    que le dashboard JARVIS était utilisé (6+ queries accumulées). Pattern d'isolation
    identique à MT-KB-L2j sur ``tests/test_vector_corrupted.py`` : ``ANALYTICS_PATH``
    redirigée vers ``tmp_path`` (fichier vide), aucun accès au vrai ``MEMORY_DIR``.
    """
    fake_path = tmp_path / "analytics.json"
    fake_path.write_text("{}")  # _load() → _migrate() → {queries: [], agents: {}, models: {}}

    monkeypatch.setattr(analytics_module, "ANALYTICS_PATH", str(fake_path))

    analytics = AnalyticsService()
    stats = analytics.get_stats()

    assert stats["total_queries"] == 0
    assert stats["success_rate"] == 0.0
    assert stats["avg_latency_ms"] == 0.0
    assert stats["agents"] == {}
    assert stats["models"] == {}


if __name__ == "__main__":
    unittest.main()
