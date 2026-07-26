from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_toast_in_send_feedback():
    app_js = (ROOT / "static" / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    assert "function sendFeedback" in app_js
    start = app_js.index("function sendFeedback")
    end = app_js.index("function sendImplicit")
    body = app_js[start:end]
    assert "toast(" in body, "sendFeedback() doit appeler toast()"


def test_toast_in_send_implicit():
    app_js = (ROOT / "static" / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    assert "function sendImplicit" in app_js
    start = app_js.index("function sendImplicit")
    end = app_js.index("async function enhanceLastAssistant")
    body = app_js[start:end]
    assert "toast(" in body, "sendImplicit() doit appeler toast()"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
