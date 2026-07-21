"""Tests AnalyticsService — track_query, get_stats, migration."""
import json

from services.analytics import AnalyticsService


class TestAnalytics:

    def test_initial_stats_empty(self, tmp_path):
        p = tmp_path / "analytics.json"
        a = AnalyticsService(path=str(p))
        stats = a.get_stats()
        assert stats["total_queries"] == 0

    def test_track_and_get_stats(self, tmp_path):
        p = tmp_path / "analytics.json"
        a = AnalyticsService(path=str(p))
        a.track_query("dev", "phi4-mini:3.8b", tokens_in=10, tokens_out=50, latency_ms=100, success=True)
        stats = a.get_stats()
        assert stats["total_queries"] == 1
        assert "dev" in stats["agents"]

    def test_get_most_used(self, tmp_path):
        p = tmp_path / "analytics.json"
        a = AnalyticsService(path=str(p))
        used = a.get_most_used()
        assert "top_agent" in used
        assert "top_model" in used

    def test_migration_from_old_format(self):
        old = {"by_agent": {"dev": 5}, "by_model": {"phi4-mini:3.8b": 3}, "total_queries": 0}
        migrated = AnalyticsService._migrate(old)
        assert migrated["agents"] == {"dev": 5}
        assert migrated["models"] == {"phi4-mini:3.8b": 3}
        assert migrated["queries"] == []

    def test_track_persistence(self, tmp_path):
        p = tmp_path / "analytics.json"
        a = AnalyticsService(path=str(p))
        a.track_query("dev", "phi4-mini:3.8b")
        data = json.loads(p.read_text())
        assert data["agents"]["dev"] == 1
