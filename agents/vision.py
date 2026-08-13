"""Agent spécialisé en analyse de texte extrait d'une image (OCR + LLM).

Hérite de :class:`GenericAgent` : en l'absence d'image, il se comporte comme
un agent texte classique (profil ``designer``). En présence d'une image dans
le contexte, il :

  1. délègue l'extraction à **RapidOCR** (``services/ocr.py``) — moteur OCR
     déterministe (ONNX), pas un modèle de langage multimodal ;
  2. confie le **texte extrait** à un LLM texte (``Qwen2.5-7B`` via
     ``VISION_ANALYSIS_MODEL``) qui répond à la consigne de l'utilisateur.

RapidOCR ne fait qu'extraire du texte (pas d'analyse). L'analyse proprement
dite est portée par le LLM texte — recréant le comportement qu'avait
``moondream`` en un seul modèle multimodal, mais en deux étapes découplées.
Le même moteur alimente aussi l'onglet Vision dédié (``POST /api/vision``).

Aucune skill n'est jamais suggérée pour la vision (le rendu final ne contient
pas de fences de code exploitables) : ``suggested_skill`` reste ``None``.
"""

from __future__ import annotations

import logging
from typing import Any, Final, Protocol, cast

from agents.base import AgentRunResult
from agents.generic import GenericAgent
from services.ocr import run_ocr
from services.sanitize import strip_data_uri
from services.selector import DEFAULT_FALLBACK_MODEL

_logger = logging.getLogger("jarvis.agents.vision")

# ---------------------------------------------------------------------------
# Constantes de configuration de l'agent (évite les magic strings).
# Final : immuables au niveau type-checker (pas de réassignation accidentelle).
# ---------------------------------------------------------------------------

PROFILE_KEY: Final[str] = "designer"
VISION_DOMAIN_PROMPT: Final[str] = "Tu es un expert en analyse visuelle."
OCR_BACKEND_NAME: Final[str] = "rapidocr"

# Modèle texte utilisé pour analyser le texte OCR (généraliste, multilingue FR).
# Impasse volontaire sur un modèle vision : RapidOCR extrait, le LLM analyse.
VISION_ANALYSIS_MODEL: Final[str] = DEFAULT_FALLBACK_MODEL

# Consigne système de l'étape d'analyse (post-OCR).
VISION_ANALYSIS_SYSTEM: Final[str] = (
    "Tu es un analyste visuel. On te donne le texte extrait (via OCR, parfois "
    "imparfait) d'une image et la consigne de l'utilisateur. Réponds "
    "précisément en t'appuyant sur ce texte, sans inventer d'élément absent."
)

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
        """Extrait le texte de l'image (OCR) puis l'analyse via LLM, ou traite la tâche en mode texte."""
        image_data = context.get(_IMAGE_CONTEXT_KEY)
        if image_data:
            response = self._run_vision(task, image_data)
            backend = self.model_provider.get_active_backend()
            model_out = VISION_ANALYSIS_MODEL
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

    def _run_vision(self, task: str, image_data: str) -> str:
        """OCR (extraction) puis analyse LLM du texte extrait."""
        ocr_result = self._run_ocr(image_data)
        if ocr_result["error"]:
            return f"⚠️ {ocr_result['error']}"
        text = ocr_result["text"]
        if not text.strip():
            return "⚠️ Aucun texte détecté dans l'image."
        prompt = f"Consigne : {task}\n\nTexte extrait de l'image :\n{text}"
        try:
            return self.model_provider.query(prompt, VISION_ANALYSIS_MODEL, system=VISION_ANALYSIS_SYSTEM)
        except Exception as e:  # noqa: BLE001 - dégradation gracieuse vers l'OCR brut
            _logger.warning("Analyse LLM échouée, repli OCR brut : %s", e)
            return cast(str, text)

    def _run_ocr(self, image_data: str) -> dict[str, Any]:
        """Extraction de texte via RapidOCR (déterministe, hors LLM)."""
        image_b64 = strip_data_uri(image_data)
        result = run_ocr(image_b64)
        if result["error"]:
            _logger.warning("OCR échoué : %s", result["error"])
        return result

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


__all__ = [
    "VisionAgent",
    "PROFILE_KEY",
    "VISION_DOMAIN_PROMPT",
    "OCR_BACKEND_NAME",
    "VISION_ANALYSIS_MODEL",
    "VISION_ANALYSIS_SYSTEM",
]
