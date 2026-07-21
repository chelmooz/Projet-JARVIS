"""Protocols — Types duck pour les adapters backend LLM (remplace ports.adapter)."""
from abc import ABC, abstractmethod

from models import Result


class LLMAdapter(ABC):
    """Contrat ABC pour les adapters backend LLM (Ollama, Shimmy)."""

    @abstractmethod
    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        ...

    @abstractmethod
    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict:
        ...

    @abstractmethod
    def chat(self, model: str, messages: list[dict]) -> Result:
        ...

    @abstractmethod
    def is_available(self, model: str) -> bool:
        ...

    @abstractmethod
    def first_available(self) -> str | None:
        ...

    @abstractmethod
    def get_active_backend(self) -> str:
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        ...

    @abstractmethod
    def embed(self, text: str, model: str | None = None) -> list[float]:
        ...

    @abstractmethod
    def ping(self) -> bool:
        ...
