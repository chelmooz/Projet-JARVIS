from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_index_html_sans_toggle_consent():
    index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="s-diagnostic-consent"' not in index_html, (
        "Le toggle de consentement diagnostic doit avoir été retiré (C1)"
    )
    assert 'id="consent-status"' not in index_html, (
        "Le statut de consentement doit avoir été retiré (C1)"
    )
    assert "Diagnostic externe" not in index_html, (
        "Le groupe Settings « Diagnostic externe » doit avoir été retiré (C1)"
    )


def test_app_js_sans_logique_consent():
    app_js = (ROOT / "static" / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    for func in ("restoreConsentState", "setConsentStatus"):
        assert f"function {func}" not in app_js, (
            f"La fonction {func}() doit avoir été supprimée de app.js (C1)"
        )
    assert "s-diagnostic-consent" not in app_js, (
        "Le toggle de consentement doit être absent de app.js (C1)"
    )


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
