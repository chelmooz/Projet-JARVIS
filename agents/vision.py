"""Agent spécialisé en analyse d'images et vision par ordinateur.

Hérite de :class:`GenericAgent` : en l'absence d'image, il se comporte comme
un agent texte classique (profil ``designer``). En présence d'une image dans
le contexte, il bascule sur l'appel multimodal du fournisseur d'inférence.

Aucune skill n'est jamais suggérée pour la vision (le rendu visuel ne contient
pas de fences de code exploitables) : ``suggested_skill`` reste ``None``.
"""

from __future__ import annotations

import logging
from typing import Any, Final, Protocol

from agents.base import AgentRunResult
from agents.generic import GenericAgent

_logger = logging.getLogger("jarvis.agents.vision")

# ---------------------------------------------------------------------------
# Constantes de configuration de l'agent (évite les magic strings).
# Final : immuables au niveau type-checker (pas de réassignation accidentelle).
# ---------------------------------------------------------------------------

PROFILE_KEY: Final[str] = "designer"
VISION_DOMAIN_PROMPT: Final[str] = "Tu es un expert en analyse visuelle."

# Clé du contexte portant l'image encodée (cohérent avec JarvisRequest.image
# et l'injection effectuée par le graph). Ne pas renommer sans migration.
_IMAGE_CONTEXT_KEY: Final[str] = "image"


# ---------------------------------------------------------------------------
# Contrat du fournisseur d'inférence (ISP : ajoute query_multimodal au
# sous-ensemble requis par GenericAgent).
# ---------------------------------------------------------------------------

class _VisionModelProvider(Protocol):
    """Sous-ensemble d'inférence requis par l'agent vision (texte + image)."""

    def query(self, prompt: str, model: str, system: str | None = None) -> str: ...
    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict | str: ...
    def get_active_backend(self) -> str: ...


class VisionAgent(GenericAgent):
    """Agent vision : multimodal si image présente, texte sinon."""

    def __init__(
        self,
        model_provider: _VisionModelProvider,
        memory: Any | None = None,
    ) -> None:
        super().__init__(
            model_provider,
            memory,
            profile_key=PROFILE_KEY,
            domain_prompt=VISION_DOMAIN_PROMPT,
        )

    def run(self, task: str, model: str, context: dict[str, Any]) -> AgentRunResult:
        """Analyse l'image du contexte, ou traite la tâche en mode texte."""
        image_data = context.get(_IMAGE_CONTEXT_KEY)
        response = (
            self._run_multimodal(model, task, image_data)
            if image_data
            else self._run_text(model, task, context)
        )
        return {
            "agent": self._profile_key,
            "model": model,
            "backend": self.model_provider.get_active_backend(),
            "response": response,
            "suggested_skill": None,
        }

    # ------------------------------------------------------------------
    # Branches d'exécution
    # ------------------------------------------------------------------

    def _run_multimodal(self, model: str, task: str, image_data: str) -> str:
        """Appel multimodal ; extrait la chaîne de réponse du payload."""
        result = self.model_provider.query_multimodal(model, task, image_data)
        return self._extract_response(result)

    def _run_text(
        self, model: str, task: str, context: dict[str, Any],
    ) -> str:
        """Repli texte : prompt de domaine vision via l'héritage GenericAgent."""
        system, user = self._build_messages(
            self._profile_key, task, context, default_prompt=self._domain_prompt,
        )
        return self.model_provider.query(user, model, system=system)

    # ------------------------------------------------------------------
    # Normalisation du payload multimodal
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_response(result: dict | str) -> str:
        """Extrait la réponse d'un payload multimodal (dict ``{"content": ...}`` ou str).

        Le backend renvoie soit un dict (``{"content", "model", "role"}``), soit
        directement une chaîne selon la version d'Ollama : on normalise les deux.
        Un payload inattendu dégénère en chaîne vide mais est loggé en warning
        (dégradation observable, pas muette).
        """
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str):
                return content
            _logger.warning(
                "Payload multimodal : 'content' non-str (%s)", type(content).__name__,
            )
            return ""
        if isinstance(result, str):
            return result
        # Garde-fou runtime : le backend Ollama n'est pas typé statiquement.
        _logger.warning(
            "Payload multimodal inattendu (%s), réponse vide", type(result).__name__,
        )
        return ""


__all__ = ["VisionAgent", "PROFILE_KEY", "VISION_DOMAIN_PROMPT"]
