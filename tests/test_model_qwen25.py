
import pytest
from starlette.testclient import TestClient

# Test live : nécessite le modèle Qwen2.5-7B Ollama réellement disponible.
pytestmark = pytest.mark.live

from controllers.router import app  # Assurez-vous que votre application FastAPI est importée ici

client = TestClient(app)

def test_qwen25_chat():
    # Simuler une requête à l'API pour une conversation avec le modèle Qwen2.5
    response = client.post(
        "/api/chat",
        json={
            "model": "Qwen/Qwen2.5-7B-Instruct-GGUF",
            "messages": [
                {"role": "user", "content": "Quelle est la capitale de la France ?"}
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0

def test_qwen25_vectorize_fallback():
    # Simuler une requête à l'API pour la vectorisation avec le modèle Qwen2.5 (fallback)
    response = client.post(
        "/api/vectorize",
        json={
            "model": "Qwen/Qwen2.5-7B-Instruct-GGUF",
            "text": "Ceci est un texte pour tester le fallback de vectorisation."
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "embedding" in data
    assert isinstance(data["embedding"], list)
    assert len(data["embedding"]) > 0 # La dimension exacte peut varier pour un fallback
    assert all(isinstance(x, float) for x in data["embedding"])
