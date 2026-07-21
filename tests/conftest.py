"""Configuration pytest — Ajoute le projet au PYTHONPATH et gère les tests live.

Un test marqué `@pytest.mark.live` (ou via `pytestmark = pytest.mark.live`)
nécessite un service réel (Ollama, un modèle, Playwright…). Ces tests sont
automatiquement ignorés hors-ligne : soit via la variable d'environnement
`JARVIS_OFFLINE_TESTS=1`, soit si aucun serveur Ollama n'est joignable.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ollama_disponible() -> bool:
    """Vérifie si un serveur Ollama répond (port JARVIS 11436 / système 11434)."""
    # Import paresseux : on évite toute dépendance lourde au démarrage de pytest
    import httpx

    for port in (11436, 11434):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/tags", timeout=1).status_code == 200:
                return True
        except Exception:
            pass
    return False


def pytest_configure(config):
    # Marqueur pour les tests nécessitant un service live (Ollama, modèle, Playwright…)
    config.addinivalue_line(
        "markers",
        "live: test nécessitant un service live (Ollama, modèle réel, Playwright)",
    )


def pytest_collection_modifyitems(config, items):
    # Hors-ligne (variable d'env OU Ollama injoignable) → on skippe les tests live
    offline_force = os.environ.get("JARVIS_OFFLINE_TESTS") == "1"
    offline = offline_force or not _ollama_disponible()
    if not offline:
        return
    skip_live = pytest.mark.skip(
        reason="Test live ignoré hors-ligne (Ollama injoignable / JARVIS_OFFLINE_TESTS=1)"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
