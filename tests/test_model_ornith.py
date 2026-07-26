
import pytest
from starlette.testclient import TestClient

# Test live : nécessite le modèle DeepHat-V1-7B Ollama réellement disponible.
pytestmark = pytest.mark.live

from controllers.router import app  # Assurez-vous que votre application FastAPI est importée ici

client = TestClient(app)

MODEL = "hf.co/mradermacher/DeepHat-V1-7B-i1-GGUF:Q4_K_M"

def test_deephat_chat_generation():
    # Simuler une requête à l'API pour une conversation avec le modèle DeepHat
    response = client.post(
        "/api/chat",
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "Analyse ce log pour des menaces de securite."}
            ]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0

