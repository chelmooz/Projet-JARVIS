from pathlib import Path

import pytest

STYLE_CSS = Path(__file__).parent.parent / "static" / "assets" / "css" / "style.css"


def test_dead_css_classes_removed():
    """Vérifie que les classes CSS mortes de l'ancien design Outils sont supprimées"""
    css = STYLE_CSS.read_text(encoding="utf-8")

    dead_classes = [
        ".tool-card",
        ".tool-card .name",
        ".tool-card .desc",
        ".tool-card .actions",
        ".btn-run",
        ".btn-dl",
        ".badge-fallback",
    ]

    found = []
    for cls in dead_classes:
        if cls in css:
            found.append(cls)

    assert not found, f"Classes CSS mortes encore présentes dans style.css: {found}"


def test_tools_tab_still_works():
    """Vérifie que les classes actuelles de l'onglet Outils sont présentes"""
    css = STYLE_CSS.read_text(encoding="utf-8")

    # Classes utilisées par refreshTools() dans app.js
    current_classes = [
        ".tools-section",
        ".tools-item",
        ".tools-key",
        ".tools-val",
        ".tools-grid",
        ".tools-empty",
    ]

    for cls in current_classes:
        assert cls in css, f"Classe actuelle {cls} manquante dans style.css"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
