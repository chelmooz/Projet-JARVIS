"""InferenceService — Façade unifiée pour l'inférence LLM (Ollama)."""

from __future__ import annotations

import logging
from typing import Any

from models import Result
from ports import (
    ChatPort,
    EmbeddingPort,
    ModelRegistryPort,
    MultimodalPort,
)
from services.adapters import AdapterRegistry
from services.adapters.protocols import LLMAdapter

_logger = logging.getLogger("jarvis.inference")


class InferenceService(ChatPort, MultimodalPort, EmbeddingPort, ModelRegistryPort):
    """Façade unifiée pour l'inférence LLM (backend unique: Ollama).

    Implémente les ports granulaires (ISP) :
    - ChatPort : génération de texte (query, chat)
    - MultimodalPort : analyse d'images (query_multimodal)
    - EmbeddingPort : calcul d'embeddings (embed)
    - ModelRegistryPort : découverte de modèles (list_models, is_available, etc.)
    """

    def __init__(self) -> None:
        self._registry = AdapterRegistry()

    def _adapter(self) -> LLMAdapter:
        """Retourne l'adaptateur Ollama (singleton géré par le registre)."""
        return self._registry.get()

    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        """Envoie un prompt textuel au modèle et retourne la réponse brute."""
        return self._adapter().query(prompt, model, system)

    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict[str, Any]:
        """Envoie un prompt multimodal (texte + image) au modèle."""
        return self._adapter().query_multimodal(model, prompt, image_base64)

    def chat(self, model: str, messages: list[dict[str, Any]]) -> Result:
        """Envoie une conversation structurée (historique de messages)."""
        return self._adapter().chat(model, messages)

    def is_available(self, model: str) -> bool:
        """Vérifie si un modèle est disponible sur le backend actif."""
        return self._adapter().is_available(model)

    def resolve_model(self, model: str) -> str | None:
        """Résout un nom court de config vers le tag Ollama réel (None si absent)."""
        return self._adapter().resolve_model(model)

    def first_available(self) -> str | None:
        """Retourne le premier modèle disponible sur le backend actif."""
        return self._adapter().first_available()

    def get_active_backend(self) -> str:
        """Retourne le nom du backend actif (délègue à l'adaptateur pour respecter le DIP)."""
        return self._adapter().get_active_backend()

    def list_models(self) -> list[str]:
        """Retourne les modèles disponibles sur le backend actif."""
        return self._adapter().list_models()

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Génère un embedding vectoriel pour le texte donné."""
        return self._adapter().embed(text, model)

    def ping(self) -> bool:
        """Vérifie si le backend Ollama est accessible."""
        return self._adapter().ping()

    def is_healthy(self) -> bool:
        """Vérifie que le backend Ollama répond (santé du service d'inférence)."""
        try:
            return self.ping()
        except Exception:
            _logger.warning("Inference health check failed", exc_info=True)
            return False

    def close(self) -> None:
        """Libère l'adaptateur (fermeture déterministe du client HTTP à l'arrêt)."""
        self._adapter().close()

    def cancel_current(self, thread_id: int) -> None:
        """Annule la requête d'inférence du thread donné (timeout agent).

        ROADMAP 14.1 : à la place de fermer le client HTTP global (qui coupait
        aussi les requêtes concurrentes en vol), annule **uniquement** la
        requête du thread fourni — le pool partagé et les autres requêtes
        restent intacts (keep-alive TCP conservé).
        """
        try:
            self._adapter().cancel_request(thread_id)
        except Exception as e:  # noqa: BLE001 - annulation best-effort
            _logger.warning("cancel_current: échec annulation requête du thread %s: %s", thread_id, e)

    def is_streaming(self) -> bool:
        """Un flux SSE est-il actif (sink posé sur ce thread) ?"""
        adapter = self._adapter()
        sink = getattr(adapter, "_stream_sink_var", None)
        if sink is not None:
            try:
                return sink.get() is not None
            except LookupError:
                return False
        return False

    def set_stream_sink(self, sink: Any) -> None:
        """Active le streaming des tokens vers ``sink`` (ROADMAP 14.2)."""
        self._adapter().set_stream_sink(sink)

    def clear_stream_sink(self) -> None:
        """Désactive le streaming (retour au mode JSON complet)."""
        self._adapter().clear_stream_sink()


__all__ = ["InferenceService"]
