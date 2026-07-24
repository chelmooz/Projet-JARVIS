"""Routes JARVIS — Endpoint principal POST /api/jarvis et helpers."""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from controllers.context import get_app_context
from controllers.di import AppContext
from models.schemas import JarvisRequest
from services.sanitize import clean_text, validate_base64_image
from services.selector import read_preferences

_logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 10000
MAX_IMAGE_MB = 4
TRUNCATE_CONV_ID = 64

router = APIRouter()


def _save_conv(
    conv_id: str | None,
    task: str,
    result: dict,
    agent_key: str,
    conversations_svc,
) -> None:
    """Persiste la conversation (user + assistant) si un conv_id est fourni."""
    if not conv_id:
        return
    try:
        conversations_svc.add_message(conv_id, "user", task)
        resp = result.get("response") if isinstance(result, dict) else str(result)
        conversations_svc.add_message(
            conv_id, "assistant", resp or "",
            agent=result.get("agent", agent_key),
            model=result.get("model"),
        )
    except Exception as e:
        _logger.error("save_conv failed: %s", e)


def _track_query(
    agent_key: str,
    model_name: str,
    result: dict,
    start: float,
    analytics_svc,
    task: str = "",
) -> None:
    """Enregistre les métriques d'une requête.

    Les tokens_in reflètent la tâche envoyée par l'utilisateur,
    pas la réponse du modèle (correction P1 #8 audit 2026-07-21).
    """
    latency = round((time.time() - start) * 1000, 1)
    analytics_svc.track_query(
        agent=agent_key,
        model=model_name,
        tokens_in=len(str(task)) // 4,
        tokens_out=len(str(result.get("response", ""))) // 4,
        latency_ms=latency,
        success=result.get("error") is None,
    )


@router.get("/api/jarvis")
async def jarvis_info():
    """Documentation des endpoints disponibles."""
    return {
        "endpoints": {
            "POST /api/jarvis": "Envoyer une tâche à JARVIS",
            "GET /api/status": "Statut des services",
            "POST /api/vision": "Analyser une image",
            "GET /api/agents": "Liste des profils",
            "POST /api/agents/assign": "Assigner un modèle à un profil",
            "POST /api/ingest": "Ingérer des documents",
            "GET /api/conversations": "Lister les conversations",
            "POST /api/conversations": "Créer une conversation",
            "GET /api/analytics": "Statistiques d'usage",
            "GET /api/cyber/workflows": "Workflows cybersécurité",
            "GET /api/pipelines": "Lister les pipelines disponibles",
            "POST /api/pipelines/run": "Exécuter un pipeline",
            "GET /api/backend": "Backend actif",
            "POST /api/backend/select": "Changer de backend",
            "GET /api/metrics": "Métriques d'usage et uptime",
            "GET /api/models": "Modèles disponibles sur le backend actif",
            "GET /api/settings": "Lire les préférences utilisateur",
            "PUT /api/settings": "Modifier une préférence utilisateur",
            "POST /api/files/authorize": "Autoriser un dossier pour analyse",
            "DELETE /api/files/authorize": "Révoquer un dossier",
            "GET /api/files/authorized": "Lister dossiers autorisés",
            "POST /api/files/list": "Lister contenu d'un dossier",
            "POST /api/files/read": "Lire un fichier (max 10 Ko)",
            "POST /api/files/find": "Chercher fichiers par pattern glob",
        }
    }


@router.post("/api/jarvis")
async def handle_request(
    body: JarvisRequest,
    context: AppContext = Depends(get_app_context),
):
    """Endpoint principal de traitement d'une tâche JARVIS."""
    try:
        prefs = read_preferences()
        if prefs.get("offline", False):
            return {
                "response": "Mode hors-ligne activé. Désactivez le mode hors-ligne dans les paramètres.",
                "agent": "system",
                "model": "offline",
                "backend": "offline",
            }

        orchestrator = context.orchestrator
        if orchestrator is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "JARVIS n'est pas encore prêt (services non initialisés — "
                             "Ollama injoignable ou init en échec). Réessayez dans quelques secondes.",
                    "agent": "system",
                    "model": "unknown",
                },
            )

        task = clean_text(body.task, MAX_TEXT_LENGTH)
        image = body.image
        if image and not validate_base64_image(image, max_mb=MAX_IMAGE_MB):
            image = None

        conv_id = body.conversation_id
        if conv_id:
            conv_id = conv_id.strip()[:TRUNCATE_CONV_ID]

        start = time.time()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, orchestrator.handle_request, task, image, conv_id
        )

        agent_key = result.get("agent", "unknown")
        model_name = result.get("model", "auto")

        _track_query(agent_key, model_name, result, start, context.analytics, task=task)
        _save_conv(conv_id, task, result, agent_key, context.conversations)

        return result

    except Exception:
        _logger.error("handle_request crashed", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Erreur interne du service", "agent": "system", "model": "unknown"},
        )


__all__ = ["router"]
