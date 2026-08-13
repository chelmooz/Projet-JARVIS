"""Agent spécialisé en extraction de texte depuis une image (OCR).

Hérite de :class:`GenericAgent` : en l'absence d'image, il se comporte comme
un agent texte classique (profil ``designer``). En présence d'une image dans
le contexte, il délègue à **RapidOCR** (``services/ocr.py``) — moteur OCR
déterministe (ONNX), pas un modèle de langage multimodal.

Historique : cet agent appelait auparavant ``query_multimodal()`` sur un
modèle vision Ollama (``moondream``). Ce modèle n'est plus installé/assigné
(voir ``services/ocr.py`` pour le détail du remplacement) ; router l'image
vers RapidOCR ici évite de dépendre d'un modèle absent — le même moteur
alimente aussi l'onglet Vision dédié (``POST /api/vision``).

Aucune skill n'est jamais suggérée pour la vision (le rendu OCR ne contient
pas de fences de code exploitables) : ``suggested_skill`` reste ``None``.
"""

from __future__ import annotations

import logging
from typing import Any, Final, Protocol

from agents.base import AgentRunResult
from agents.generic import GenericAgent
from services.ocr import run_ocr
from services.sanitize import strip_data_uri

_logger = logging.getLogger("jarvis.agents.vision")

# ---------------------------------------------------------------------------
# Constantes de configuration de l'agent (évite les magic strings).
# Final : immuables au niveau type-checker (pas de réassignation accidentelle).
# ---------------------------------------------------------------------------

PROFILE_KEY: Final[str] = "designer"
VISION_DOMAIN_PROMPT: Final[str] = "Tu es un expert en analyse visuelle."
OCR_BACKEND_NAME: Final[str] = "rapidocr"

# Clé du contexte portant l'image encodée (cohérent avec JarvisRequest.image
# et l'injection effectuée par le graph). Ne pas renommer sans migration.
_IMAGE_CONTEXT_KEY: Final[str] = "image"


# ---------------------------------------------------------------------------
# Contrat du fournisseur d'inférence (texte uniquement désormais : le
# multimodal n'est plus utilisé, l'image passe par RapidOCR).
# ---------------------------------------------------------------------------


class _VisionModelProvider(Protocol):
    """Sous-ensemble d'inférence requis par l'agent vision (texte uniquement)."""

    def query(self, prompt: str, model: str, system: str | None = None) -> str: ...
    def get_active_backend(self) -> str: ...


class VisionAgent(GenericAgent):
    """Agent vision : OCR (RapidOCR) si image présente, texte sinon."""

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
        self.model_provider: _VisionModelProvider = model_provider

    def run(self, task: str, model: str, context: dict[str, Any]) -> AgentRunResult:
        """Extrait le texte de l'image du contexte (OCR), ou traite la tâche en mode texte."""
        image_data = context.get(_IMAGE_CONTEXT_KEY)
        if image_data:
            response = self._run_ocr(image_data)
            backend = OCR_BACKEND_NAME
            model_out = OCR_BACKEND_NAME
        else:
            response = self._run_text(model, task, context)
            backend = self.model_provider.get_active_backend()
            model_out = model
        return {
            "agent": self._profile_key,
            "model": model_out,
            "backend": backend,
            "response": response,
            "suggested_skill": None,
        }

    # ------------------------------------------------------------------
    # Branches d'exécution
    # ------------------------------------------------------------------

    def _run_ocr(self, image_data: str) -> str:
        """Extraction de texte via RapidOCR (déterministe, hors LLM)."""
        image_b64 = strip_data_uri(image_data)
        result = run_ocr(image_b64)
        if result["error"]:
            _logger.warning("OCR échoué : %s", result["error"])
            return f"⚠️ {result['error']}"
        text = result["text"]
        return text if text.strip() else "⚠️ Aucun texte détecté dans l'image."

    def _run_text(
        self,
        model: str,
        task: str,
        context: dict[str, Any],
    ) -> str:
        """Repli texte : prompt de domaine vision via l'héritage GenericAgent."""
        system, user = self._build_messages(
            self._profile_key,
            task,
            context,
            default_prompt=self._domain_prompt,
        )
        return self.model_provider.query(user, model, system=system)


__all__ = ["VisionAgent", "PROFILE_KEY", "VISION_DOMAIN_PROMPT", "OCR_BACKEND_NAME"]
