"""OllamaAdapter — Backend LLM via Ollama API native (Facade).

Implémente LLMAdapter en déléguant à :
- OllamaHTTPClient (transport, retry, streaming, cancellation)
- ModelRegistry (découverte/résolution modèles, keep_alive policy)
- EmbeddingsClient (embed, embed_batch)

Surface publique inchangée : mêmes méthodes, signatures, exceptions.
"""

import logging
import os
from typing import Any

import httpx

from config.constants import PROJECT_DIR
from models import Result
from services.adapters.embeddings import EmbeddingsClient
from services.adapters.http import BudgetExceededError, OllamaHTTPClient
from services.adapters.models import ModelRegistry
from services.adapters.protocols import LLMAdapter

_logger = logging.getLogger("jarvis.adapters.ollama")

ADAPTERS_PATH = os.path.join(PROJECT_DIR, "config", "adapters.yaml")


class OllamaAdapter(LLMAdapter):
    """Façade OllamaAdapter — compose HTTP, Models, Embeddings."""

    def __init__(self, base_url: str | None = None, max_retries: int = 3):
        self._http_client = OllamaHTTPClient(base_url=base_url, max_retries=max_retries)
        self._models = ModelRegistry(self._http_client)
        self._embeddings = EmbeddingsClient(self._http_client, self._models)
        self._backend = "ollama"

    @property
    def _http(self) -> httpx.Client:
        """Pool HTTP partagé — conservé pour compatibilité tests existants."""
        return self._http_client._get_http()

    @_http.setter
    def _http(self, client: httpx.Client) -> None:
        """Setter pour tests — remplace le pool partagé."""
        self._http_client._http = client

    @property
    def _request_clients(self) -> dict[int, httpx.Client]:
        """Proxy vers le client HTTP pour compatibilité tests (streaming)."""
        return self._http_client._request_clients

    def set_stream_sink(self, sink: Any) -> None:
        self._http_client.set_stream_sink(sink)

    def clear_stream_sink(self) -> None:
        self._http_client.clear_stream_sink()

    def close(self) -> None:
        self._http_client.close()

    def ping(self) -> bool:
        return self._http_client.ping()

    def cancel_request(self, thread_id: int) -> None:
        self._http_client.cancel_request(thread_id)

    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self._models.keep_alive_for(model),
        }
        if system:
            payload["system"] = system
        sink = self._http_client._stream_sink_var.get()
        if sink is not None:
            payload["stream"] = True
            return self._http_client._call_streaming(
                f"{self._http_client._base_url}/api/generate", payload, key="response"
            )
        data = self._http_client._call_with_retry(f"{self._http_client._base_url}/api/generate", payload)
        return str(data.get("response", ""))

    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "images": [image_base64],
            "keep_alive": self._models.keep_alive_for(model),
        }
        data = self._http_client._call_with_retry(f"{self._http_client._base_url}/api/generate", payload)
        return {"content": str(data.get("response", "")), "model": model, "role": "assistant"}

    def chat(self, model: str, messages: list[dict[str, Any]]) -> Result:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": self._models.keep_alive_for(model),
        }
        sink = self._http_client._stream_sink_var.get()
        if sink is not None:
            payload["stream"] = True
            try:
                content = self._http_client._call_streaming(
                    f"{self._http_client._base_url}/api/chat", payload, key="message"
                )
                return Result.ok(data={"content": content, "role": "assistant"}, agent="system", model=model)
            except RuntimeError as e:
                return Result.fail(error=str(e), agent="system", model=model)
        try:
            data = self._http_client._call_with_retry(f"{self._http_client._base_url}/api/chat", payload)
            content = str(data.get("message", {}).get("content", ""))
            return Result.ok(data={"content": content, "role": "assistant"}, agent="system", model=model)
        except RuntimeError as e:
            return Result.fail(error=str(e), agent="system", model=model)

    def list_models(self) -> list[str]:
        return self._models.list_models()

    def is_available(self, model: str) -> bool:
        return self._models.is_available(model)

    def resolve_model(self, model: str) -> str | None:
        return self._models.resolve_model(model)

    def first_available(self) -> str | None:
        return self._models.first_available()

    def embed(self, text: str, model: str | None = None) -> list[float]:
        return self._embeddings.embed(text, model)

    def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return self._embeddings.embed_batch(texts, model)

    def get_active_backend(self) -> str:
        return self._backend


# Ré-export pour compatibilité imports existants
__all__ = ["OllamaAdapter", "BudgetExceededError"]
