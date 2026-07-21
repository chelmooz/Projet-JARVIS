
import pytest
from starlette.testclient import TestClient

# Test live : nécessite le modèle Ornith-1.0-9B Ollama réellement disponible.
pytestmark = pytest.mark.live

from controllers.router import app  # Assurez-vous que votre application FastAPI est importée ici

client = TestClient(app)

def test_ornith_chat_generation():
    # Simuler une requête à l'API pour une conversation avec le modèle Ornith
    response = client.post(
        "/api/chat",
        json={
            "model": "deepreinforce-ai/Ornith-1.0-9B-GGUF",
            "messages": [
                {"role": "user", "content": "Bonjour, quel est le temps aujourd'hui ?"}
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
    # Ajoutez des assertions plus spécifiques sur le format ou le contenu si nécessaire

