
import pytest
from starlette.testclient import TestClient

# Test live : nécessite un modèle de vision Ollama réellement disponible.
pytestmark = pytest.mark.live

from controllers.router import app  # Assurez-vous que votre application FastAPI est importée ici

client = TestClient(app)

def test_llama_vision_describe_image():
    # Simuler une requête à l'API pour la description d'image avec le modèle Llama-Vision
    # Cela nécessiterait un endpoint API capable de prendre une image en entrée
    # Pour cet exemple, nous allons simuler une réponse ou un appel à un endpoint mocké
    # Si votre API a un endpoint spécifique pour la vision, ajustez l'URL et le payload
    response = client.post(
        "/api/vision/describe",
        json={
            "model": "leafspark/Llama-3.2-11B-Vision-Instruct-GGUF:Q4_K_M",
            "image_url": "https://example.com/image.jpg", # URL d'image fictive
            "prompt": "Décris cette image en détail."
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "description" in data
    assert isinstance(data["description"], str)
    assert len(data["description"]) > 0
    # Ajoutez des assertions plus spécifiques sur le contenu de la description si possible

