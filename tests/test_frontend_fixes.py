# tests/test_frontend_fixes.py
"""
Tests pour valider les correctifs frontend v5.4.1 :
1. Bug Markdown (regex sécurisée + escHtml)
2. Performance Chart.js (update vs destroy)
3. Nettoyage CSP & syntaxe (suppression des espaces fautifs)
"""
import re
from pathlib import Path


def test_rendermarkdown_regex_valid():
    """Vérifie que renderMarkdown est sécurisé et que les regex sont intactes."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")
    assert "function renderMarkdown(text)" in app_js
    assert "escHtml(text)" in app_js, "escHtml doit être appelé pour prévenir les XSS"
    assert r"/```(\w*)\n([\s\S]*?)```/g" in app_js, "Regex des blocs de code manquante ou cassée"

def test_chartjs_no_destroy():
    """Vérifie que destroyCharts() a été supprimé pour éviter les fuites mémoire."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")
    assert "destroyCharts()" not in app_js, "L'appel à destroyCharts() doit être supprimé"

def test_chartjs_update_or_create_exists():
    """Vérifie que la nouvelle fonction de réutilisation des instances Chart.js est présente."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")
    assert "function updateOrCreateChart(" in app_js, "Fonction updateOrCreateChart() introuvable"
    assert "chart.update()" in app_js, "La fonction doit utiliser .update() pour réutiliser l'instance"

def test_no_spaces_in_html_attributes():
    """Vérifie qu'il n'y a pas d'espaces fautifs dans les attributs HTML (ex: class= \")."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")

    # \s+ capture 1 ou plusieurs espaces (cible spécifiquement les erreurs comme class= ")
    invalid_patterns = [
        r'class=\s+"',      # class= "
        r'data-\w+=\s+"',   # data-xxx= "
        r'id=\s+"',         # id= "
    ]

    for pattern in invalid_patterns:
        matches = re.findall(pattern, app_js)
        assert len(matches) == 0, f"Espaces fantômes détectés: {pattern} ({len(matches)} occurrences)"

def test_eschtml_used_in_rendermarkdown():
    """Vérifie que l'échappement HTML est bien en place."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")
    assert "escHtml(text)" in app_js or "escHtml(s)" in app_js

def test_no_syntax_errors():
    """Vérifie qu'il n'y a pas d'erreurs de syntaxe JS dues à des espaces cassés."""
    app_js = Path("static/assets/js/app.js").read_text(encoding="utf-8")

    # \s+ capture les espaces fautifs (ex: = > au lieu de =>)
    invalid_patterns = [
        r'=\s+>',            # = > (espace entre = et >)
        r'querySel\s+ectorAll', # querySel ectorAll
        r'a\s+wait\s+\w+',   # a wait
    ]

    for pattern in invalid_patterns:
        matches = re.findall(pattern, app_js)
        assert len(matches) == 0, f"Erreur de syntaxe détectée: {pattern} ({len(matches)} occurrences)"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
