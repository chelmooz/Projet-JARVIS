"""Tests des métriques de ressources (mémoire/CPU) — AUDIT-P3.3."""
from services import metrics as metrics_mod
from services.metrics import MetricsService


class TestResourceUsage:
    """Tests get_resource_usage() et champs /api/metrics."""

    def test_get_resource_usage_keys(self):
        # La fonction doit exister et renvoyer un dict avec les bonnes clés
        usage = metrics_mod.get_resource_usage()
        assert isinstance(usage, dict)
        assert "memory_rss_mb" in usage
        assert "cpu_percent" in usage
        assert "psutil_available" in usage
        assert usage["psutil_available"] in (True, False)

    def test_metrics_endpoint_includes_resource_fields(self):
        # /api/metrics doit exposer les champs ressources (même si None)
        m = MetricsService()
        data = m.get_metrics()
        assert "memory_rss_mb" in data
        assert "cpu_percent" in data
        assert "psutil_available" in data
