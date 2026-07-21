"""Tests TDD — AUDIT-P2.4 : headers de cache sur les fichiers statiques.

RED : ces tests échouent tant que controllers/router.py ne pose pas
Cache-Control / ETag sur les réponses d'assets statiques.
"""
from fastapi.testclient import TestClient

from controllers.router import app

client = TestClient(app)


class TestStaticCacheHeaders:
    # ── Cache-Control sur le HTML (SPA) ──────────────────────────────────

    def test_index_html_a_cache_control(self):
        # / sert index.html — doit porter un header Cache-Control.
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Cache-Control" in resp.headers
        assert "max-age" in resp.headers["Cache-Control"]

    def test_index_html_path_a_cache_control(self):
        resp = client.get("/index.html")
        assert resp.status_code == 200
        assert "Cache-Control" in resp.headers

    # ── Cache-Control sur les assets JS (.js -> 3600s) ───────────────────

    def test_js_asset_cache_control_3600(self):
        resp = client.get("/monkey-engine.js")
        assert resp.status_code == 200
        cc = resp.headers.get("Cache-Control", "")
        assert "public" in cc
        assert "max-age=3600" in cc

    def test_js_asset_path_static_cache_control(self):
        resp = client.get("/static/monkey-engine.js")
        assert resp.status_code == 200
        cc = resp.headers.get("Cache-Control", "")
        assert "public" in cc
        assert "max-age=3600" in cc

    # ── ETag + réponse 304 sur If-None-Match ─────────────────────────────

    def test_etag_present_sur_js(self):
        resp = client.get("/monkey-engine.js")
        assert "ETag" in resp.headers

    def test_etag_304_si_if_none_match(self):
        first = client.get("/monkey-engine.js")
        etag = first.headers.get("ETag")
        assert etag
        second = client.get("/monkey-engine.js", headers={"If-None-Match": etag})
        assert second.status_code == 304

    def test_pas_de_cache_sur_api(self):
        # Les endpoints API ne doivent pas recevoir de Cache-Control statique.
        resp = client.get("/api/jarvis")
        assert "Cache-Control" not in resp.headers
