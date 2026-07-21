"""Tests MetricsService."""
from services.metrics import MetricsService


class TestMetricsService:

    def test_initial_metrics(self):
        m = MetricsService()
        metrics = m.get_metrics()
        assert "uptime_seconds" in metrics
        assert "requests" in metrics
        assert metrics["requests"] >= 0

    def test_incr_requests(self):
        m = MetricsService()
        before = m.get_metrics()["requests"]
        m.incr_requests()
        assert m.get_metrics()["requests"] >= before + 1

    def test_incr_pipeline_run(self):
        m = MetricsService()
        before = m.get_metrics()["pipeline_runs"]
        m.incr_pipeline_run()
        assert m.get_metrics()["pipeline_runs"] >= before + 1

    def test_incr_errors(self):
        m = MetricsService()
        before = m.get_metrics()["errors"]
        m.incr_errors()
        assert m.get_metrics()["errors"] >= before + 1

    def test_by_endpoint(self):
        m = MetricsService()
        m.incr_requests("/api/test")
        stats = m.get_metrics()
        assert stats["by_endpoint"].get("/api/test", 0) >= 1

    def test_uptime_human_format(self):
        assert MetricsService._format_uptime(3661) == "1h 1m 1s"
        assert MetricsService._format_uptime(0) == "0h 0m 0s"
