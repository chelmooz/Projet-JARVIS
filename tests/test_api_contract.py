"""Tests for frontend ↔ backend API contract (P5 Ch1).

Detects drift: frontend fetch() calls that have no matching backend route.
"""

from scripts.check_api_contract import (
    compute_drift,
    extract_backend_routes,
    extract_frontend_calls,
)


def _get_app():
    """Import the real FastAPI app (lazy to avoid circular imports at module level)."""
    import os
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from controllers.router import app
    return app


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestExtractFrontendCalls:
    """Ch1.1 — extract_frontend_calls()"""

    def test_extract_simple_get(self):
        """A plain fetch('/api/status') should yield GET /api/status."""
        html = '<script>fetch("/api/status")</script>'
        assert extract_frontend_calls(html) == {("GET", "/api/status")}

    def test_extract_post_with_method(self):
        """fetch('/api/jarvis', { method: 'POST' }) should yield POST /api/jarvis."""
        html = """<script>fetch('/api/jarvis', { method: 'POST', body: '{}' })</script>"""
        assert extract_frontend_calls(html) == {("POST", "/api/jarvis")}

    def test_extract_multiple_calls(self):
        """Multiple fetch calls with different methods."""
        html = """
        <script>
            fetch('/api/status')
            fetch('/api/jarvis', { method: 'POST' })
            fetch('/api/conversations', { method: 'DELETE' })
        </script>
        """
        expected = {("GET", "/api/status"), ("POST", "/api/jarvis"), ("DELETE", "/api/conversations")}
        assert extract_frontend_calls(html) == expected

    def test_extract_with_trailing_slash(self):
        """Trailing slashes should be normalized."""
        html = '<script>fetch("/api/status/")</script>'
        assert extract_frontend_calls(html) == {("GET", "/api/status")}

    def test_extract_empty_html(self):
        """Empty HTML should yield empty set."""
        assert extract_frontend_calls("") == set()

    def test_extract_no_fetch_calls(self):
        """HTML without fetch() calls."""
        assert extract_frontend_calls("<html><body>Hello</body></html>") == set()


class TestExtractBackendRoutes:
    """Ch1.2 — extract_backend_routes()"""

    def test_extract_returns_set_of_tuples(self):
        """Should return non-empty set with (method, path) tuples from the real app."""
        routes = extract_backend_routes(_get_app())
        assert isinstance(routes, set)
        assert all(isinstance(r, tuple) and len(r) == 2 for r in routes)
        # Should contain at least the core endpoints
        assert ("GET", "/api/status") in routes
        assert ("POST", "/api/jarvis") in routes

    def test_excludes_openapi_docs_redoc(self):
        """Routes like /openapi.json, /docs, /redoc should be excluded."""
        routes = extract_backend_routes(_get_app())
        excluded = {("/openapi.json",), ("/docs",), ("/redoc",)}
        for r in routes:
            path = r[1] if isinstance(r, tuple) else r
            assert not any(path.startswith(p[0]) for p in excluded)


# ---------------------------------------------------------------------------
# Integration test: frontend ↔ backend drift detection
# ---------------------------------------------------------------------------

class TestNoFrontendBackendDrift:
    """Ch1.3 — detect calls that exist in frontend but NOT in backend."""

    def test_no_frontend_backend_drift(self):
        """Every frontend fetch() call must have a matching backend route.

        F1 (frontend appelait /api/files/drives et /api/files/browse sans route)
        est résolu : les routes existent. Le backend select (no-op) a été retiré
        (YAGNI single-backend), le frontend ne l'appelle plus.
        """
        app = _get_app()
        frontend = extract_frontend_calls()
        backend = extract_backend_routes(app)
        drift = compute_drift(frontend, backend)
        assert drift == set(), f"Frontend-backend drift detected: {drift}"
