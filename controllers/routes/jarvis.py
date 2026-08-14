"""Routes JARVIS — Endpoint principal POST /api/jarvis et helpers."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from controllers.context import get_app_context
from controllers.di import AppContext
from models.schemas import JarvisRequest
from services.orchestrator import OrchestratorService
from services.sanitize import clean_text, validate_base64_image
from services.selector import read_preferences
from services.streaming import StreamSink

_logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 10000
MAX_IMAGE_MB = 4
TRUNCATE_CONV_ID = 64

router = APIRouter()


def _save_conv(
    conv_id: str | None,
    task: str,
    result: dict[str, Any],
    agent_key: str,
    conversations_svc: Any,
) -> None:
    """Persiste la conversation (user + assistant) si un conv_id est fourni."""
    if not conv_id:
        return
    try:
        conversations_svc.add_message(conv_id, "user", task)
        resp = result.get("response") if isinstance(result, dict) else str(result)
        conversations_svc.add_message(
            conv_id,
            "assistant",
            resp or "",
            agent=result.get("agent", agent_key),
            model=result.get("model"),
        )
    except Exception as e:
        _logger.error("save_conv failed: %s", e)


def _track_query(
    agent_key: str,
    model_name: str,
    result: dict[str, Any],
    start: float,
    analytics_svc: Any,
    task: str = "",
    source: str = "chat",
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
        source=source,
    )


@router.get("/api/jarvis")
async def jarvis_info() -> dict[str, Any]:
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


def _offline_response(prefs: dict[str, Any]) -> dict[str, Any] | None:
    """Renvoie la réponse system du mode hors-ligne, ou ``None`` si en ligne."""
    if not prefs.get("offline", False):
        return None
    return {
        "response": "Mode hors-ligne activé. Désactivez le mode hors-ligne dans les paramètres.",
        "agent": "system",
        "model": "offline",
        "backend": "offline",
    }


def _service_unavailable_response() -> JSONResponse:
    """503 : orchestrateur pas encore initialisé (Ollama injoignable ou init en échec)."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "JARVIS n'est pas encore prêt (services non initialisés — "
            "Ollama injoignable ou init en échec). Réessayez dans quelques secondes.",
            "agent": "system",
            "model": "unknown",
        },
    )


def _parse_request_input(body: JarvisRequest) -> tuple[str, str | None, str | None, str]:
    """Nettoie et normalise les champs du payload : ``(task, image, conv_id, source)``."""
    task = clean_text(body.task, MAX_TEXT_LENGTH)

    image = body.image
    if image and not validate_base64_image(image, max_mb=MAX_IMAGE_MB):
        image = None

    conv_id = body.conversation_id
    if conv_id:
        conv_id = conv_id.strip()[:TRUNCATE_CONV_ID]

    return task, image, conv_id, body.source


async def _run_and_record(
    orchestrator: OrchestratorService,
    context: AppContext,
    task: str,
    image: str | None,
    conv_id: str | None,
    start: float,
    source: str,
) -> dict[str, Any]:
    """Exécute l'orchestrateur (chemin non-streamé) puis journalise métriques + conversation."""
    result = await orchestrator.handle_request(task, image, conv_id)

    agent_key = result.get("agent", "unknown")
    model_name = result.get("model", "auto")

    await asyncio.to_thread(
        _track_query, agent_key, model_name, result, start, context.analytics, task=task, source=source
    )
    await asyncio.to_thread(_save_conv, conv_id, task, result, agent_key, context.conversations)

    return result


@router.post("/api/jarvis")
async def handle_request(
    body: JarvisRequest,
    request: Request,
    context: AppContext = Depends(get_app_context),
) -> Any:
    """Endpoint principal de traitement d'une tâche JARVIS.

    Négociation SSE (ROADMAP 14.2) : si le client envoie
    ``Accept: text/event-stream`` et qu'aucun flux n'est déjà actif, la
    réponse est un flux d'événements (``token`` puis ``done``) ; sinon le
    comportement JSON complet historique est conservé à l'identique.
    """
    try:
        prefs = await asyncio.to_thread(read_preferences)
        offline_response = _offline_response(prefs)
        if offline_response is not None:
            return offline_response

        orchestrator = context.orchestrator
        if orchestrator is None:
            return _service_unavailable_response()

        task, image, conv_id, source = _parse_request_input(body)
        start = time.time()
        loop = asyncio.get_running_loop()
        wants_stream = "text/event-stream" in request.headers.get("accept", "")

        if wants_stream:
            return await _handle_request_streamed(
                loop,
                orchestrator,
                context,
                task,
                image,
                conv_id,
                start,
                source,
            )

        return await _run_and_record(orchestrator, context, task, image, conv_id, start, source)

    except Exception:
        _logger.error("handle_request crashed", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Erreur interne du service", "agent": "system", "model": "unknown"},
        )


async def _handle_request_streamed(
    loop: asyncio.AbstractEventLoop,
    orchestrator: OrchestratorService,
    context: AppContext,
    task: str,
    image: str | None,
    conv_id: str | None,
    start: float,
    source: str = "chat",
) -> StreamingResponse:
    """Exécute le pipeline et renvoie un flux SSE des tokens du modèle.

    Un ``StreamSink`` est posé sur l'inférence le temps de la génération :
    l'adaptateur pousse chaque token (thread executor → sink thread-safe) et
    le générateur SSE les relaie au client au fil de l'eau (TTFT ≈ premier
    token). L'événement final ``done`` porte le résultat complet.
    """
    sink = StreamSink()
    assert context.inference is not None
    context.inference.set_stream_sink(sink)

    async def _generate() -> None:
        result: dict[str, Any] | None = None
        try:
            result = await orchestrator.handle_request(task, image, conv_id)
            agent_key = result.get("agent", "unknown")
            model_name = result.get("model", "auto")
            await asyncio.to_thread(
                _track_query, agent_key, model_name, result, start, context.analytics, task=task, source=source
            )
            await asyncio.to_thread(_save_conv, conv_id, task, result, agent_key, context.conversations)
        except Exception as e:  # noqa: BLE001 - l'erreur part dans l'événement done
            _logger.error("handle_request streamed crashed", exc_info=True)
            result = {"response": f"Erreur interne du service: {e}", "agent": "system", "model": "unknown"}
        finally:
            sink.finish(result)

    asyncio.ensure_future(_generate())

    async def _iter_events() -> AsyncIterator[str]:
        try:
            async for event in sink.events():
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        finally:
            assert context.inference is not None
            context.inference.clear_stream_sink()

    return StreamingResponse(
        _iter_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
