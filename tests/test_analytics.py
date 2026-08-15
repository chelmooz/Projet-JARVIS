#!/usr/bin/env python3
"""Test that analytics stats work correctly."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.analytics import AnalyticsService


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

    def test_analytics_no_queries(self):
        """GREEN: Sans requêtes, les stats sont vides/zeros."""
        analytics = AnalyticsService()
        stats = analytics.get_stats()
        self.assertEqual(stats["total_queries"], 0)
        self.assertEqual(stats["success_rate"], 0.0)
        self.assertEqual(stats["avg_latency_ms"], 0.0)
        self.assertEqual(stats["agents"], {})
        self.assertEqual(stats["models"], {})


if __name__ == "__main__":
    unittest.main()
