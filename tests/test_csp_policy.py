"""Lot 5.3 — Politique CSP (verrou de régression, TDD).

Le header ``Content-Security-Policy`` doit :
- ne JAMAIS contenir ``'unsafe-inline'`` (script-src / style-src) ;
- porter un nonce (les scripts/styles inline, s'il en existe, exigeraient le
  nonce) ; ``request.state.csp_nonce`` est exposé sur la requête pour
  d'éventuels besoins de templating.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from controllers.router import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_csp_header_present_with_nonce() -> None:
    resp = _client().get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert csp.startswith("default-src 'self'")
    assert "script-src 'self' 'nonce-" in csp
    assert "style-src 'self' 'nonce-" in csp


def test_csp_forbids_unsafe_inline() -> None:
    resp = _client().get("/")
    csp = resp.headers["Content-Security-Policy"]
    assert "unsafe-inline" not in csp


def test_csp_nonce_stable_link_with_x_frame_options() -> None:
    resp = _client().get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
