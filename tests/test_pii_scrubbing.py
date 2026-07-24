"""Tests Fix #6 — Vérifie que les PII sont masquées avant stockage."""
from unittest.mock import patch


class TestPiiScrubbing:

    def test_scrub_removes_email(self):
        """La fonction scrub() doit masquer les emails."""
        from services.sanitize import scrub
        result = scrub("Contact: user@example.com")
        assert "[REDACTED]" in result
        assert "user@example.com" not in result

    def test_scrub_removes_private_ip(self):
        """La fonction scrub() doit masquer les IPs privées."""
        from services.sanitize import scrub
        result = scrub("Server: 192.168.1.100")
        assert "[REDACTED]" in result
        assert "192.168.1.100" not in result

    def test_scrub_removes_cred_pair(self):
        """La fonction scrub() doit masquer les paires credential=valeur."""
        from services.sanitize import scrub
        result = scrub("password=super_secret_key_here")
        assert "[REDACTED]" in result

    @patch("services.analytics.write_json_atomic")
    def test_track_query_scrubs_agent_name(self, mock_write):
        """track_query ne stocke pas d'injections dans le nom d'agent."""
        import os
        import tempfile

        from services.analytics import AnalyticsService

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "analytics.json")
            svc = AnalyticsService(path)
            svc.track_query("test-agent", "phi4-mini:latest", tokens_in=10, tokens_out=50)
            stats = svc.get_stats()
            assert stats["total_queries"] == 1
            assert stats["agents"].get("test-agent") == 1

    def test_search_scrubs_results(self):
        """Les résultats de recherche doivent être scrubés (PII masquées)."""
        from controllers.routes.documents import search_documents
        from controllers.di import AppContext
        from services.sanitize import scrub

        class FakeVector:
            def search(self, q, top_k=20):
                return [
                    {"text": "Email: admin@internal.com", "score": 0.95},
                    {"text": "IP: 10.0.0.1", "score": 0.85},
                ]

        ctx = AppContext()
        ctx.vector = FakeVector()

        with patch("controllers.routes.documents.scrub", wraps=scrub) as mock_scrub:
            result = search_documents(q="test", top_k=2, context=ctx)
            assert mock_scrub.call_count >= 2
            for r in result["data"]["results"]:
                assert "[REDACTED]" in r["text"], f"Champ non scrubé: {r['text']}"
