import re
import pytest
from pathlib import Path

STATIC_DIR = Path(__file__).parent.parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"
APP_JS = STATIC_DIR / "assets" / "js" / "app.js"
STYLE_CSS = STATIC_DIR / "assets" / "css" / "style.css"


def test_hamburger_button_exists_in_html():
    """Vérifie la présence du bouton hamburger dans index.html"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="hamburger"' in html, "Bouton #hamburger absent du HTML"
    assert 'aria-label="Ouvrir le menu"' in html, "aria-label manquant sur #hamburger"
    assert 'class="sidebar-backdrop"' in html, "Overlay .sidebar-backdrop absent du HTML"


def test_sidebar_has_show_class_toggle_in_css():
    """Vérifie que le CSS définit .sidebar.show et .sidebar-backdrop.show"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert ".sidebar.show" in css, "Règle .sidebar.show absente du CSS"
    assert ".sidebar-backdrop.show" in css, "Règle .sidebar-backdrop.show absente du CSS"


def test_hamburger_toggle_handler_exists_in_js():
    """Vérifie la présence du handler click sur #hamburger dans app.js"""
    js = APP_JS.read_text(encoding="utf-8")
    # Vérifie présence d'un handler click sur #hamburger qui toggle .show
    assert "getElementById('hamburger')" in js or 'getElementById("hamburger")' in js, "Référence à #hamburger absente du JS"
    assert "classList.toggle('show')" in js, "classList.toggle('show') absent du JS"
    # Vérifie aussi le toggle sur backdrop
    assert "sidebarBackdrop" in js or "sidebar-backdrop" in js, "Référence au backdrop absente"
    assert "classList.toggle('show')" in js, "Toggle backdrop manquant"


def test_media_query_hamburger_display_block():
    """Vérifie que le CSS affiche le hamburger sous 768px"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert "@media (max-width: 768px)" in css, "Media query 768px absente"
    # Il y a deux media queries 768px dans le CSS, on cherche celle qui contient #hamburger { display: block }
    # La seconde (mobile sidebar) est à la fin du fichier
    last_media_idx = css.rfind("@media (max-width: 768px)")
    media_query_section = css[last_media_idx:last_media_idx + 500]
    assert "#hamburger" in media_query_section, "#hamburger non ciblé dans media query 768px (mobile sidebar)"
    assert "display: block" in media_query_section, "display: block manquant pour #hamburger"
    assert "display: block" in media_query_section, "display: block manquant pour #hamburger"


def test_sidebar_close_on_backdrop_click():
    """Vérifie que le click sur le backdrop ferme la sidebar"""
    js = APP_JS.read_text(encoding="utf-8")
    # Vérifie qu'un click sur le backdrop retire la classe show
    assert "sidebarBackdrop" in js or "sidebar-backdrop" in js, "Variable backdrop non définie"
    assert "classList.remove('show')" in js or "classList.toggle('show')" in js, "Fermeture sidebar absente"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])