"""Tests du client Ollama local (``agents/ollama_client.py``).

HTTP entièrement mocké — aucun appel réseau réel.
"""

from unittest.mock import patch

import httpx

from agents.ollama_client import generate_json, unload


def test_generate_json_returns_parsed_dict():
    """Réponse avec bloc ```json``` → dict extrait."""
    with patch("agents.ollama_client.httpx.post") as mock_post:
        mock_post.return_value.json.return_value = {"response": 'Voici le résultat:\n```json\n{"verdict": "GO"}\n```'}
        assert generate_json("prompt") == {"verdict": "GO"}


def test_generate_json_returns_none_on_invalid_json():
    """Réponse sans JSON → None."""
    with patch("agents.ollama_client.httpx.post") as mock_post:
        mock_post.return_value.json.return_value = {"response": "Pas de JSON ici"}
        assert generate_json("prompt") is None


def test_generate_json_returns_none_on_http_error():
    """Exception HTTP (timeout, connexion refusée) → None, pas de levée."""
    with patch("agents.ollama_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("refused")
        assert generate_json("prompt") is None


def test_unload_returns_true_on_success():
    """Réponse 200 → True."""
    with patch("agents.ollama_client.httpx.post"):
        assert unload() is True


def test_unload_returns_false_on_error():
    """Exception HTTP → False."""
    with patch("agents.ollama_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("blocked")
        assert unload() is False
