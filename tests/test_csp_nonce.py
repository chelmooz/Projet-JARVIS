"""Tests CSP Nonce — Phase 1 TDD (RED → GREEN → REFACTOR)."""

import re
import secrets

from fastapi.testclient import TestClient

from controllers.context import _ctx
from controllers.router import app

client = TestClient(app)


def _apply_mocks():
    """Injecte des fakes minimaux dans le contexte pour les tests HTTP."""
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


def extract_nonce(csp_header: str) -> str:
    match = re.search(r"'nonce-([^']+)'", csp_header)
    return match.group(1) if match else ""


# ============================================================
# MT-1.1 : Test RED — vérifie l'absence de nonce dans le CSP
#           actuel (échec attendu → on implémente ensuite)
# ============================================================

def test_csp_header_contains_nonce():
    """RED : le CSP header doit contenir un nonce (échoue tant que
    le middleware n'est pas implémenté)."""
    _apply_mocks()
    resp = client.get("/api/backend")
    csp = resp.headers.get("Content-Security-Policy", "")
    nonce = extract_nonce(csp)
    assert nonce, f"Aucun nonce trouvé dans CSP: {csp[:100]}..."
    assert nonce != "", "Le nonce ne doit pas être vide"


def test_csp_nonce_unique_per_request():
    """RED : chaque requête doit avoir un nonce différent."""
    _apply_mocks()
    resp1 = client.get("/api/backend")
    resp2 = client.get("/api/backend")
    nonce1 = extract_nonce(resp1.headers.get("Content-Security-Policy", ""))
    nonce2 = extract_nonce(resp2.headers.get("Content-Security-Policy", ""))
    assert nonce1 != nonce2, "Les nonces doivent être uniques par requête"


def test_csp_no_unsafe_inline():
    """RED : le CSP ne doit plus contenir 'unsafe-inline'."""
    _apply_mocks()
    resp = client.get("/api/backend")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "'unsafe-inline'" not in csp, (
        f"'unsafe-inline' encore présent dans CSP: {csp}"
    )


def test_csp_nonce_format_valid():
    """RED : le nonce doit être une chaîne base64url valide (16 bytes)."""
    _apply_mocks()
    resp = client.get("/api/backend")
    csp = resp.headers.get("Content-Security-Policy", "")
    nonce = extract_nonce(csp)
    assert nonce, "Nonce absent"
    # 16 bytes en base64url = 22 caractères (sans padding)
    assert len(nonce) == 22, f"Longueur nonce attendue 22, obtenue {len(nonce)}: {nonce}"
    # Vérifier que c'est du base64url valide
    assert re.match(r"^[A-Za-z0-9_-]+$", nonce), f"Format nonce invalide: {nonce}"


def test_csp_header_present():
    """RED : le header Content-Security-Policy doit être présent."""
    _apply_mocks()
    resp = client.get("/api/backend")
    assert "Content-Security-Policy" in resp.headers, (
        "Header CSP absent"
    )


# ============================================================
# Phase 2 : index.html — plus de styles inline (MT-2.1)
# ============================================================

def test_index_html_no_inline_display_none():
    """MT-2.1 : index.html ne doit plus contenir style="display:none"."""
    with open("static/index.html", encoding="utf-8") as f:
        content = f.read()
    assert 'style="display:none"' not in content, (
        "style=display:none encore présent dans index.html"
    )


def test_index_html_uses_d_none_class():
    """MT-2.3 : les 4 éléments cachés utilisent class="d-none"."""
    with open("static/index.html", encoding="utf-8") as f:
        content = f.read()
    # Vérifier les 4 occurrences
    assert 'class="d-none"' in content or 'class="d-none"' in content, (
        "Aucun élément avec class=d-none"
    )
    # Compter les class="d-none" (fb-back a deux classes: "fb-back d-none")
    count_d_none = content.count('class="d-none"') + content.count('d-none"')
    # Au moins 3 éléments distincts avec d-none
    assert count_d_none >= 3, (
        f"Moins de 3 éléments avec d-none, trouvé {count_d_none}"
    )


# ============================================================
# Phase 3 : app.js — plus de styles inline (MT-3.1)
# ============================================================

def test_app_js_no_inline_styles():
    """MT-3.1 : app.js ne doit plus contenir d'attributs style= dans les templates."""
    with open("static/assets/js/app.js", encoding="utf-8") as f:
        content = f.read()
    # Vérifier l'absence de style= dans les template strings
    assert 'style="' not in content, (
        "style= encore présent dans app.js"
    )


def test_app_js_no_onclick():
    """MT-4.1 : app.js ne doit plus contenir d'attributs onclick=."""
    with open("static/assets/js/app.js", encoding="utf-8") as f:
        content = f.read()
    assert 'onclick=' not in content, (
        "onclick= encore présent dans app.js"
    )


def test_app_js_uses_css_classes():
    """MT-3.4 : app.js utilise les classes CSS utilitaires."""
    with open("static/assets/js/app.js", encoding="utf-8") as f:
        content = f.read()
    assert 'model-meta' in content, "model-meta non utilisé"
    assert 'agent-btn-primary' in content, "agent-btn-primary non utilisé"
    assert 'path-row' in content, "path-row non utilisé"
    assert 'path-name' in content, "path-name non utilisé"
    assert 'revoke-btn' in content, "revoke-btn non utilisé"
    assert 'error-label' in content, "error-label non utilisé"
    assert 'empty-paths' in content, "empty-paths non utilisé"


def test_app_js_uses_data_attributes():
    """MT-4.2 : app.js utilise les data-* attributes pour la délégation."""
    with open("static/assets/js/app.js", encoding="utf-8") as f:
        content = f.read()
    assert 'data-conv-id=' in content, "data-conv-id non utilisé"
    assert 'data-del-conv-id=' in content, "data-del-conv-id non utilisé"
    assert 'data-revoke-path=' in content, "data-revoke-path non utilisé"