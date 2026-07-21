"""AdapterRegistry — Fabrique d'adapters backend LLM (backend unique: Ollama)."""
from services.adapters.ollama_adapter import OllamaAdapter
from services.adapters.protocols import LLMAdapter


class AdapterRegistry:
    """AdapterRegistry — retourne toujours l'adaptateur Ollama."""

    def __init__(self):
        self._adapter = OllamaAdapter()

    def get(self, name: str | None = None) -> LLMAdapter:
        """Get — ignore name, toujours Ollama."""
        return self._adapter
