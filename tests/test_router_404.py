"""Tests TDD pour la gestion des 404 dans router.py.

Scénario RED-GREEN :
- RED : écrire le test avant la correction
- GREEN : corriger le code pour faire passer le test
"""
from fastapi.testclient import TestClient

from controllers.router import app


client = TestClient(app)


def test_serve_static_returns_404_for_nonexistent_path():
    """Quand on demande un chemin inexistant, le status doit être 404 (pas 200)."""
    response = client.get("/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_serve_static_returns_404_for_path_traversal():
    """Le path traversal doit être bloqué avec un 404."""
    response = client.get("/../../etc/passwd")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
