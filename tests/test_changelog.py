"""Tests — CHANGELOG.md documente les changements récents (Phases 7-9).

Garde-fou anti-régression : les sections du CHANGELOG doivent
refléter les évolutions livrées depuis v5.4.
"""

CHANGELOG_PATH = "CHANGELOG.md"


def _changelog_content() -> str:
    with open(CHANGELOG_PATH, encoding="utf-8") as f:
        return f.read()


def test_changelog_mentions_orjson():
    """CHANGELOG doit mentionner orjson (perf)."""
    content = _changelog_content()
    assert "orjson" in content, "orjson non mentionné dans CHANGELOG"


def test_changelog_mentions_ux_polish():
    """CHANGELOG doit mentionner les améliorations UX (Phase 9)."""
    content = _changelog_content()
    keywords = ["focus trap", "skeleton load", "feedback toast", "dark mode"]
    found = [kw for kw in keywords if kw in content.lower()]
    assert len(found) >= 2, (
        f"Moins de 2 améliorations UX trouvées dans CHANGELOG "
        f"(trouvé : {found})"
    )


def test_changelog_mentions_security():
    """CHANGELOG doit mentionner les correctifs sécurité (Phase 7)."""
    content = _changelog_content()
    assert "error leakage" in content.lower() or "X-XSS-Protection" in content, (
        "Correctif sécurité non mentionné dans CHANGELOG"
    )


def test_changelog_mentions_stubs_removal():
    """CHANGELOG doit mentionner la suppression des stubs legacy."""
    content = _changelog_content()
    assert "stub" in content.lower() or "_check_ollama" in content, (
        "Suppression stubs legacy non mentionnée dans CHANGELOG"
    )


def test_changelog_mentions_roadmap_update():
    """CHANGELOG doit mentionner la mise à jour de ROADMAP."""
    content = _changelog_content()
    assert "ROADMAP" in content, "Mise à jour ROADMAP non mentionnée dans CHANGELOG"
