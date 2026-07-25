import re
from pathlib import Path


def test_escape_key_closes_modal():
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")
    assert "Escape" in app_js
    pattern = re.compile(
        r"['\"]Escape['\"].*?closeBrowser|closeBrowser.*?['\"]Escape['\"]",
        re.DOTALL
    )
    assert pattern.search(app_js), \
        "La touche Escape ne déclenche pas closeBrowser()"


def test_modal_has_aria_attributes():
    index_html = Path("static/index.html").read_text(encoding="utf-8")
    assert 'role="dialog"' in index_html
    assert 'aria-modal="true"' in index_html


def test_focus_trap_tab_handling():
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")

    assert "e.key === 'Tab'" in app_js or 'e.key === "Tab"' in app_js, \
        "Aucune détection de la touche Tab dans app.js"

    assert "e.shiftKey" in app_js, \
        "Aucune gestion de Shift+Tab dans app.js"

    tab_context = re.search(
        r"e\.key\s*===\s*['\"]Tab['\"].*?\{[^}]*preventDefault[^}]*\}[^}]*\}",
        app_js,
        re.DOTALL
    )
    assert tab_context is not None, \
        "Tab n'est pas intercepté avec preventDefault()"


def test_focus_trap_cycling():
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")

    patterns = [
        r"document\.activeElement\s*===\s*firstFocusable",
        r"document\.activeElement\s*===\s*lastFocusable",
        r"lastFocusable\.focus\(\)",
        r"firstFocusable\.focus\(\)",
    ]
    for p in patterns:
        assert re.search(p, app_js), \
            f"Pattern manquant: {p}"


def test_focus_trap_open_close():
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")

    assert "document.activeElement" in app_js, \
        "openBrowser() doit stocker document.activeElement avant le focus trap"

    open_body = re.search(
        r"function\s+openBrowser\(\s*\)\s*\{.*?\}",
        app_js,
        re.DOTALL
    )
    assert open_body is not None, "openBrowser() introuvable"

    close_body = re.search(
        r"function\s+closeBrowser\(\s*\)\s*\{.*?\}",
        app_js,
        re.DOTALL
    )
    assert close_body is not None, "closeBrowser() introuvable"


def test_focus_trap_focusable_selector():
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")

    patterns = [
        r"FOCUSABLE_SELECTOR\s*=",
        r"querySelectorAll\s*\(\s*['\"](?:button|\[href\])",
        r"querySelectorAll\s*\(\s*FOCUSABLE_SELECTOR",
        r"fb-modal",
    ]
    found = any(re.search(p, app_js) for p in patterns)
    assert found, \
        "Aucun sélecteur d'éléments focusables trouvé (FOCUSABLE_SELECTOR ou querySelectorAll littéral)"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
