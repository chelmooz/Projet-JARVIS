
import pytest
from starlette.testclient import TestClient

# Test live : nécessite le modèle Phi-4-mini Ollama réellement disponible.
pytestmark = pytest.mark.live

from controllers.router import app  # Assurez-vous que votre application FastAPI est importée ici

client = TestClient(app)

def test_phi4_chat_prompt():
    # Simuler une requête à l'API pour une conversation avec le modèle Phi-4-mini
    response = client.post(
        "/api/chat",
        json={
            "model": "Melvin56/Phi-4-mini-instruct-abliterated-GGUF:Q4_K_M",
            "messages": [
                {"role": "user", "content": "Bonjour, comment allez-vous ?"}
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
    # Ajoutez des assertions plus spécifiques sur le format ou le contenu si nécessaire

