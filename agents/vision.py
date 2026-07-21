"""Agent spécialisé en analyse d'images et vision par ordinateur.

Hérite de :class:`GenericAgent` : en l'absence d'image, il se comporte comme
un agent texte classique (profil ``designer``). En présence d'une image dans
le contexte, il bascule sur l'appel multimodal du fournisseur d'inférence.

Aucune skill n'est jamais suggérée pour la vision (le rendu visuel ne contient
pas de fences de code exploitables) : ``suggested_skill`` reste ``None``.
"""

from __future__ import annotations

from typing import Any, Protocol

from agents.base import AgentRunResult
from agents.generic import GenericAgent

# ---------------------------------------------------------------------------
# Constantes de configuration de l'agent (évite les magic strings).
# ---------------------------------------------------------------------------

PROFILE_KEY: str = "designer"
VISION_DOMAIN_PROMPT: str = "Tu es un expert en analyse visuelle."

# Clé du contexte portant l'image encodée (cohérent avec JarvisRequest.image
# et l'injection effectuée par le graph). Ne pas renommer sans migration.
_IMAGE_CONTEXT_KEY: str = "image"


# ---------------------------------------------------------------------------
# Contrat du fournisseur d'inférence (ISP : ajoute query_multimodal au
# sous-ensemble requis par GenericAgent).
# ---------------------------------------------------------------------------

class _VisionModelProvider(Protocol):
    """Sous-ensemble d'inférence requis par l'agent vision (texte + image)."""

    def query(self, prompt: str, model: str, system: str | None = None) -> str: ...
    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> Any: ...
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
            "backend": self.model.get_active_backend(),
            "response": response,
            "suggested_skill": None,
        }

    # ------------------------------------------------------------------
    # Branches d'exécution
    # ------------------------------------------------------------------

    def _run_multimodal(self, model: str, task: str, image_data: str) -> str:
        """Appel multimodal ; extrait la chaîne de réponse du payload."""
        result = self.model.query_multimodal(model, task, image_data)
        return self._extract_response(result)

    def _run_text(
        self, model: str, task: str, context: dict[str, Any],
    ) -> str:
        """Repli texte : prompt de domaine vision via l'héritage GenericAgent."""
        system, user = self._build_messages(
            self._profile_key, task, context, default_prompt=self._domain_prompt,
        )
        return self.model.query(user, model, system=system)

    # ------------------------------------------------------------------
    # Normalisation du payload multimodal
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_response(result: Any) -> str:
        """Extrait la réponse d'un payload multimodal (dict ``{"content": ...}`` ou str).

        Le backend renvoie soit un dict (``{"content", "model", "role"}``), soit
        directement une chaîne selon la version d'Ollama : on normalise les deux.
        Un payload inattendu (``None``/autre) dégénère en chaîne vide plutôt que
        de propager une exception jusqu'à l'API.
        """
        if isinstance(result, dict):
            content = result.get("content")
            return content if isinstance(content, str) else ""
        return result if isinstance(result, str) else ""


__all__ = ["VisionAgent", "PROFILE_KEY", "VISION_DOMAIN_PROMPT"]
