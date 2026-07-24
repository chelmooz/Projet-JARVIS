"""Test que le warmup ne bloque pas le lifespan > 2s même si Ollama est down."""
import time
from fastapi.testclient import TestClient
from controllers.router import create_app

def test_lifespan_ready_under_2s_without_ollama():
    """Le lifespan doit démarrer en < 2s même si Ollama est injoignable."""
    app = create_app()
    start = time.time()
    with TestClient(app) as client:
        elapsed = time.time() - start
        # Le warmup vectoriel ne doit pas bloquer > 2s
        assert elapsed < 2.0, f"Lifespan bloqué {elapsed:.2f}s (warmup vectoriel ?)"
        # L'app doit être prête à accepter des requêtes
        r = client.get("/api/status")
        assert r.status_code == 200