"""InferenceService — Façade unifiée pour l'inférence LLM (Ollama)."""
from __future__ import annotations

import logging
from typing import Any

from models import Result
from ports import InferencePort
from services.adapters import AdapterRegistry

_logger = logging.getLogger("jarvis.inference")


class InferenceService(InferencePort):
    """Façade unifiée pour l'inférence LLM (backend unique: Ollama)."""

    def __init__(self) -> None:
        self._registry = AdapterRegistry()

    def _adapter(self) -> Any:
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

    def close(self) -> None:
        """Libère l'adaptateur (fermeture déterministe du client HTTP à l'arrêt)."""
        self._adapter().close()

    def cancel_current(self) -> None:
        """Annule la requête Ollama en cours (ferme le client HTTP de l'adaptateur).

        Le client est recréé paresseusement par l'adaptateur pour les appels suivants.
        Utilisé par `AgentSupervisor` au timeout pour ne pas laisser un thread
        daemon 'zombie' continuer de consommer CPU/GPU après le délai.
        """
        try:
            self._adapter().close()
        except Exception as e:  # noqa: BLE001 - annulation best-effort
            _logger.warning("cancel_current: échec fermeture adapter: %s", e)


__all__ = ["InferenceService"]
