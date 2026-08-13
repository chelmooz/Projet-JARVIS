"""EmbeddingsClient — Génération d'embeddings vectoriels via Ollama.

Extrait d'OllamaAdapter (Phase 20) : wrappers fins autour du client HTTP
et du registre de modèles pour embed() et embed_batch().
"""

import logging

from services.adapters.http import OllamaHTTPClient
from services.adapters.models import ModelRegistry

_logger = logging.getLogger("jarvis.adapters.embeddings")

DEFAULT_EMBEDDING_MODEL = "hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M"


class EmbeddingsClient:
    """Client embeddings — délègue au HTTP client et résout le modèle via le registre."""

    def __init__(self, http_client: OllamaHTTPClient, model_registry: ModelRegistry):
        self._http = http_client
        self._registry = model_registry

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Génère un embedding vectoriel pour le texte donné."""
        model = model or DEFAULT_EMBEDDING_MODEL
        model = self._registry.resolve_model(model) or model
        data = self._http._call_with_retry(
            f"{self._http._base_url}/api/embed",
            {
                "model": model,
                "input": [text],
                "keep_alive": self._registry.keep_alive_for(model),
            },
        )
        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError("Ollama embed a retourne aucun vecteur (modele d'embedding absent ou reponse partielle)")
        return list(embeddings[0])

    def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Génère des embeddings pour plusieurs textes en un seul appel HTTP.

        Utilise l'endpoint /api/embed d'Ollama qui accepte input: list[str].
        Retourne une liste de vecteurs dans le même ordre que les textes d'entrée.
        """
        if not texts:
            return []
        model = model or DEFAULT_EMBEDDING_MODEL
        model = self._registry.resolve_model(model) or model
        data = self._http._call_with_retry(
            f"{self._http._base_url}/api/embed",
            {
                "model": model,
                "input": texts,
                "keep_alive": self._registry.keep_alive_for(model),
            },
        )
        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError("Ollama embed_batch a retourne aucun vecteur")
        if len(embeddings) != len(texts):
            raise RuntimeError(f"Nombre d'embeddings ({len(embeddings)}) != nombre de textes ({len(texts)})")
        return [list(e) for e in embeddings]
