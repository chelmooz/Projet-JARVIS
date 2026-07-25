from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_theme_toggle_button_exists():
    index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="theme-toggle"' in index_html, (
        "Le bouton #theme-toggle doit exister dans index.html"
    )
    assert 'aria-label' in index_html or 'title' in index_html, (
        "Le bouton doit avoir un aria-label ou title pour l'accessibilité"
    )


def test_theme_css_light_variables():
    css = (ROOT / "static" / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    assert ':root[data-theme="light"]' in css, (
        "Le sélecteur :root[data-theme='light'] doit exister dans style.css"
    )
    for var in ("--bg", "--text", "--panel", "--border", "--text-dim"):
        assert var in css, (
            f"La variable CSS '{var}' doit être redéfinie pour le thème clair"
        )


def test_theme_js_init_and_localstorage():
    app_js = (ROOT / "static" / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    for func in ("initThemeToggle", "getTheme", "setTheme", "toggleTheme"):
        assert f"function {func}" in app_js, (
            f"La fonction {func}() doit être définie dans app.js"
        )
    assert "jarvis_theme" in app_js, (
        "La clé localStorage 'jarvis_theme' doit être utilisée"
    )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
