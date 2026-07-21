
import pytest
from starlette.testclient import TestClient

# Test live : nécessite le modèle d'embedding nomic-embed Ollama réellement disponible.
pytestmark = pytest.mark.live

from controllers.router import app  # Assurez-vous que votre application FastAPI est importée ici

client = TestClient(app)

def test_nomic_embed_vector_output():
    # Simuler une requête à l'API pour la vectorisation avec le modèle Nomic-Embed
    response = client.post(
        "/api/vectorize",
        json={
            "model": "nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M",
            "text": "Ceci est un texte à vectoriser."
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "embedding" in data
    assert isinstance(data["embedding"], list)
    assert len(data["embedding"]) == 1536  # Vérifiez la dimension attendue
    assert all(isinstance(x, float) for x in data["embedding"])
    # Ajoutez des assertions pour vérifier que les valeurs ne sont pas NaN ou infinies si nécessaire

