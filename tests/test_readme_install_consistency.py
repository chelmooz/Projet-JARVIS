"""Tests de cohérence du README pour l'installation utilisateur lambda."""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(PROJECT_ROOT, "README.md")

with open(README, encoding="utf-8") as f:
    README_TEXT = f.read()


def test_readme_documents_ollama_auto_download():
    """L'utilisateur lambda doit savoir qu'Ollama est téléchargé au 1er lancement."""
    assert "ensure_ollama_binary" in README_TEXT
    assert "n'est pas dans le dépôt" in README_TEXT or "vide au clone" in README_TEXT


def test_readme_python_version_badge_consistent():
    """Le badge Python doit refléter requires-python (>=3.10) et non 3.11 figé."""
    assert "Python-3.10%2B" in README_TEXT
    assert "Python-3.11" not in README_TEXT
    assert "Python 3.10+" in README_TEXT


def test_readme_no_stale_v50_reference():
    """Le README ne doit pas présenter l'installateur comme v5.0 (incohérent avec v5.4)."""
    # v5.4 présent, et pas de mention d'un installateur v5.0
    assert "v5.4" in README_TEXT
    assert "JARVIS Portable Edition v5.0" not in README_TEXT
