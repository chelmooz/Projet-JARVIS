"""Tests for OpenAPI contract: frontend payload keys match backend schemas (P5 Ch2).

Detects missing required fields in frontend JSON.stringify() calls.
"""
import pytest

from scripts.check_openapi_contract import (
    check_required_fields,
    extract_frontend_payload_keys,
    get_route_schemas,
)

BASELINE_XFAIL = [
    "POST /api/files/list -> path (frontend uses var)",
    "POST /api/files/read -> path (frontend uses var)",
    "POST /api/files/find -> pattern (frontend uses var)",
    "POST /api/pipelines/run -> pipeline_id, task (not called from frontend)",
    "POST /api/jarvis -> task (frontend builds body as var then stringifies)",
]


def _get_app():
    """Import the real FastAPI app (lazy)."""
    import os
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from controllers.router import app
    return app


# ---------------------------------------------------------------------------
# Unit tests for Ch2.1 — get_route_schemas
# ---------------------------------------------------------------------------

class TestGetRouteSchemas:
    """Ch2.1 — get_route_schemas()"""

    def test_returns_dict(self):
        """Should return a non-empty dict."""
        schemas = get_route_schemas(_get_app())
        assert isinstance(schemas, dict)
        assert len(schemas) > 0

    def test_jarvis_has_task_required(self):
        """POST /api/jarvis should require task."""
        schemas = get_route_schemas(_get_app())
        jarvis = schemas.get(("POST", "/api/jarvis"))
        assert jarvis is not None
        assert "task" in jarvis["required"]

    def test_vision_has_image_required(self):
        """POST /api/vision should require image."""
        schemas = get_route_schemas(_get_app())
        vision = schemas.get(("POST", "/api/vision"))
        assert vision is not None
        assert "image" in vision["required"]


# ---------------------------------------------------------------------------
# Unit tests for Ch2.2 — extract_frontend_payload_keys
# ---------------------------------------------------------------------------

class TestExtractFrontendPayloadKeys:
    """Ch2.2 — extract_frontend_payload_keys()"""

    def test_extract_simple_spread(self):
        """{ backend } should yield {'backend'}."""
        html = """<script>fetch('/api/backend/select', { method: 'POST', body: JSON.stringify({ backend }) })</script>"""
        result = extract_frontend_payload_keys(html)
        assert result.get("/api/backend/select") == {"backend"}

    def test_extract_key_value_pairs(self):
        """{ key: 'offline', value: checked } should yield {'key', 'value'}."""
        html = """<script>fetch('/api/settings', { method: 'PUT', body: JSON.stringify({ key: 'offline', value: checked }) })</script>"""
        result = extract_frontend_payload_keys(html)
        assert result.get("/api/settings") == {"key", "value"}

    def test_extract_vision_payload(self):
        """{ image: ..., task: '...' } should yield {'image', 'task'}."""
        html = """<script>fetch('/api/vision', { method: 'POST', body: JSON.stringify({ image: e.target.result, task: 'Decris' }) })</script>"""
        result = extract_frontend_payload_keys(html)
        assert result.get("/api/vision") == {"image", "task"}

    def test_extract_empty_html(self):
        """Empty HTML yields empty dict."""
        assert extract_frontend_payload_keys("") == {}


# ---------------------------------------------------------------------------
# Integration test: frontend covers all required fields
# ---------------------------------------------------------------------------

class TestFrontendCoversRequiredFields:
    """Ch2.3 — every required backend field must be sent by the frontend."""

    @pytest.mark.xfail(strict=True, reason="Baseline: 5 mismatches (frontend var extraction limit + unused routes)")
    def test_no_missing_required_fields(self):
        """All required schema fields must appear in frontend JSON.stringify payloads."""
        app = _get_app()
        schemas = get_route_schemas(app)
        frontend = extract_frontend_payload_keys()
        issues = check_required_fields(schemas, frontend)
        assert len(issues) == 0, f"Missing required fields in frontend: {issues}"


class TestCheckRequiredFields:
    """Ch2.3 helper — check_required_fields()"""

    def test_detects_missing_field(self):
        """Should report a missing required field."""
        schemas = {("POST", "/api/test"): {"schema_name": "Test", "required": ["foo"], "properties": ["foo"]}}
        frontend = {"/api/test": {"bar"}}
        issues = check_required_fields(schemas, frontend)
        assert len(issues) == 1
        assert issues[0]["missing_fields"] == ["foo"]

    def test_passes_when_all_covered(self):
        """Should pass when all required fields are present."""
        schemas = {("POST", "/api/test"): {"schema_name": "Test", "required": ["foo", "bar"], "properties": ["foo", "bar"]}}
        frontend = {"/api/test": {"foo", "bar"}}
        issues = check_required_fields(schemas, frontend)
        assert len(issues) == 0
