"""
Tests TDD pour MT-FE-3 : Skeleton Loaders (version renforcée)
Les chemins sont ancrés sur la racine du projet (parent de tests/).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_skeleton_css_exists():
    """Vérifie que les classes et l'animation skeleton existent dans le CSS."""
    css = (ROOT / "static" / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    assert ".skeleton" in css, "La classe .skeleton doit exister dans le CSS"
    assert ".skeleton-card" in css, "La classe .skeleton-card doit exister dans le CSS"
    assert "@keyframes shimmer" in css, "L'animation @keyframes shimmer doit être définie"


def test_skeleton_logic_in_app_js():
    """Vérifie que injectSkeletons() est définie ET appelée dans refreshAgents/refreshTools."""
    app_js = (ROOT / "static" / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    assert "function injectSkeletons" in app_js, "La fonction injectSkeletons() doit être définie"
    # définition (1) + appel refreshAgents (1) + refreshTools (1) + refreshSkills (1) + refreshAnalytics (1) = 5 minimum
    nb = app_js.count("injectSkeletons(")
    assert nb >= 5, (
        f"injectSkeletons() définie + appelée dans refreshAgents, refreshTools, "
        f"refreshSkills ET refreshAnalytics "
        f"(définition + 4 appels attendus, {nb} occurrence(s) trouvée(s))"
    )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])