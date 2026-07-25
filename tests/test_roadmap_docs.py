"""Tests — ROADMAP.md documente les Phases 7-9 complétées.

Garde-fou anti-régression : les sections de roadmap doivent
refléter l'état réel du projet (Phases 7-9 terminées).
"""

ROADMAP_PATH = "docs/dev-history/ROADMAP.md"


def _roadmap_content() -> str:
    with open(ROADMAP_PATH, encoding="utf-8") as f:
        return f.read()


def test_roadmap_contains_phase7_security():
    """ROADMAP.md doit mentionner la PHASE 7 — Sécurité."""
    content = _roadmap_content()
    assert "PHASE 7" in content, "PHASE 7 — Sécurité absente du ROADMAP"
    assert "SÉCURITÉ" in content or "Sécurité" in content, "Section Sécurité absente"


def test_roadmap_contains_phase8_performance():
    """ROADMAP.md doit mentionner la PHASE 8 — Performance (orjson)."""
    content = _roadmap_content()
    assert "PHASE 8" in content, "PHASE 8 — Performance absente du ROADMAP"
    assert "orjson" in content, "Section orjson absente"


def test_roadmap_contains_phase9_ux():
    """ROADMAP.md doit mentionner la PHASE 9 — Polish UX."""
    content = _roadmap_content()
    assert "PHASE 9" in content, "PHASE 9 — Polish UX absente du ROADMAP"
    assert "POLISH UX" in content or "focus trap" in content, (
        "Section Polish UX absente"
    )
