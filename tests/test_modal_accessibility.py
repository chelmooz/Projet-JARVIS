"""
Tests TDD pour MT-FE-2 : Accessibilité des modals
- Touche Escape pour fermer
- Focus trap (tabulation reste dans la modale)
"""
import re
from pathlib import Path


def test_escape_key_closes_modal():
    """Vérifie qu'un listener keydown gère la touche Escape pour fermer la modale."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")
    
    # Doit y avoir un listener global keydown qui détecte Escape
    assert "Escape" in app_js or '"Escape"' in app_js or "'Escape'" in app_js, \
        "Aucune détection de la touche Escape dans app.js"
    
    # Le listener doit appeler closeBrowser()
    # On cherche un pattern comme : if (e.key === 'Escape') closeBrowser()
    escape_pattern = re.compile(
        r"['\"]Escape['\"].*?closeBrowser|closeBrowser.*?['\"]Escape['\"]",
        re.DOTALL
    )
    assert escape_pattern.search(app_js), \
        "La touche Escape ne déclenche pas closeBrowser()"


def test_focus_trap_elements_defined():
    """Vérifie qu'il existe une logique de focus trap dans la modale."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")
    
    # Doit y avoir une notion d'éléments focusables dans la modale
    focusable_keywords = [
        "focusable",
        "querySelectorAll",  # pour récupérer les éléments focusables
        "tabindex",
    ]
    
    # Au moins un de ces mots-clés doit apparaître dans le contexte de la modale
    has_focus_logic = any(
        keyword in app_js for keyword in focusable_keywords
    )
    assert has_focus_logic, \
        "Aucune logique de focus trap détectée (focusable/tabindex/querySelectorAll)"


def test_modal_has_aria_attributes():
    """Vérifie que la modale a des attributs ARIA pour l'accessibilité."""
    index_html = Path("static/index.html").read_text(encoding="utf-8")
    
    # La modale doit avoir role="dialog" et aria-modal="true"
    assert 'role="dialog"' in index_html or "role='dialog'" in index_html, \
        "La modale n'a pas role='dialog'"
    
    assert 'aria-modal="true"' in index_html or "aria-modal='true'" in index_html, \
        "La modale n'a pas aria-modal='true'"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])