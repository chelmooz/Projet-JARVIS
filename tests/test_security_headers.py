"""Tests de sécurité — Headers HTTP de sécurité.

Garde-fou anti-régression : vérifie la présence/absence des headers
de sécurité sur les réponses de l'API.

Contexte :
- X-XSS-Protection est déprécié (ignoré des navigateurs modernes) :
  ne doit PAS être envoyé.
- X-Content-Type-Options: nosniff  DOIT être présent.
- X-Frame-Options: DENY            DOIT être présent.
"""

from fastapi.testclient import TestClient

from controllers.context import _ctx
from controllers.router import app

client = TestClient(app)


def _apply_mocks():
    from unittest.mock import MagicMock
    _ctx._initialized = True
    _ctx.inference = MagicMock()
    _ctx.memory = MagicMock()
    _ctx.vector = MagicMock()
    _ctx.conversations = MagicMock()
    _ctx.agents = {k: MagicMock() for k in ("cyber", "dev", "network", "hardware", "vision")}
    _ctx.log = MagicMock()
    _ctx.analytics = MagicMock()
    _ctx.metrics = MagicMock()
    _ctx.orchestrator = MagicMock()
    _ctx.toolbox = MagicMock()
    _ctx.router_svc = MagicMock()


XSS_LINE = "- ``X-XSS-Protection`` est déprécié"


def test_x_xss_protection_header_absent():
    """Le header X-XSS-Protection ne doit pas être présent (déprécié)."""
    _apply_mocks()
    resp = client.get("/api/backend")
    assert "x-xss-protection" not in resp.headers, (
        "X-XSS-Protection est déprécié et ne doit pas être envoyé "
        f"(trouvé : {resp.headers.get('x-xss-protection')})"
    )


def test_x_content_type_options_present():
    """Le header X-Content-Type-Options: nosniff doit être présent."""
    _apply_mocks()
    resp = client.get("/api/backend")
    assert "x-content-type-options" in resp.headers, (
        "X-Content-Type-Options doit être présent"
    )
    assert resp.headers["x-content-type-options"] == "nosniff", (
        f"X-Content-Type-Options doit être 'nosniff', "
        f"obtenu : {resp.headers['x-content-type-options']}"
    )


def test_x_frame_options_present():
    """Le header X-Frame-Options: DENY doit être présent."""
    _apply_mocks()
    resp = client.get("/api/backend")
    assert "x-frame-options" in resp.headers, (
        "X-Frame-Options doit être présent"
    )
    assert resp.headers["x-frame-options"] == "DENY", (
        f"X-Frame-Options doit être 'DENY', "
        f"obtenu : {resp.headers['x-frame-options']}"
    )


def test_x_xss_protection_debt_comment_removed():
    """Le commentaire de dette sur X-XSS-Protection dans middlewares.py
    doit être supprimé (il est obsolète : le header n'est plus envoyé)."""
    with open("controllers/middlewares.py", encoding="utf-8") as f:
        content = f.read()
    assert XSS_LINE not in content, (
        "Le commentaire de dette X-XSS-Protection doit être supprimé "
        "de middlewares.py (le header n'est plus envoyé)"
    )
