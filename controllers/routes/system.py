"""Routes système — Endpoints de monitoring (/api/health, /api/status).

Ce module regroupe les endpoints système pour le monitoring et la santé de l'application.
Extrait de controllers/router.py (dette signalée l.7-14) pour respecter SRP.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from controllers.router import _get_context
from controllers.status import build_status
from services.profiling import get_slow_endpoints

_logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# Health Check (Nouveau endpoint pour déploiement propre)
# =============================================================================


@router.get("/api/health")
async def health(request: Request) -> JSONResponse:
    """Endpoint de santé pour le monitoring.

    Retourne l'état de santé de tous les services critiques :
    - ollama: Backend d'inférence
    - inference: Service d'inférence
    - vector: Index vectoriel
    - memory: Service de mémoire
    - conversations: Service de conversations
    - version: Version de JARVIS

    Utilisé par les load balancers et outils de monitoring (Kubernetes, Docker, etc.).
    """
    context = _get_context(request)

    # Vérifier chaque service
    def check_service(name: str, service: Any) -> bool:
        """Vérifie si un service est en bonne santé."""
        check = getattr(service, "is_healthy", None)
        if check is None:
            return False
        try:
            return bool(check())
        except Exception:
            _logger.warning(f"Health check failed for {name}", exc_info=True)
            return False

    inference = getattr(context, "inference", None)
    ollama_up = False
    if inference is not None and hasattr(inference, "ping"):
        try:
            ollama_up = bool(inference.ping())
        except Exception:
            _logger.warning("Inference ping failed", exc_info=True)
            ollama_up = False

    status = {
        "ollama": ollama_up,
        "inference": check_service("inference", inference),
        "vector": check_service("vector", getattr(context, "vector", None)),
        "memory": check_service("memory", getattr(context, "memory", None)),
        "conversations": check_service("conversations", getattr(context, "conversations", None)),
        "version": "6.0",  # À synchroniser avec config.constants.VERSION
    }

    # Vérifier si tout est OK
    all_healthy = all(status.values())

    if all_healthy:
        return JSONResponse(status_code=200, content={"status": status, "healthy": True})
    else:
        return JSONResponse(status_code=503, content={"status": status, "healthy": False})


# =============================================================================
# Status Stream — SSE (remplace le polling 5s côté client)
# =============================================================================


async def _status_generator(request: Request, max_duration: int = 60) -> AsyncIterator[str]:
    """Génère un flux SSE alimenté par le cache de statut.

    Envoie un ping initial (commentaire SSE) pour confirmer la connexion,
    puis le statut actuel depuis app.state.status_cache. Le flux reste ouvert
    en envoyant des heartbeats toutes les 15s, puis se termine après 60s — le
    client SSE gère automatiquement la reconnexion (retry: 5000).

    max_duration (60s par défaut) : durée du flux avant fermeture.
    """
    context = _get_context(request)
    cache = request.app.state.status_cache
    lock = request.app.state.status_lock

    # Ping initial pour confirmer la connexion SSE
    # (sse_starlette formate deja les lignes "data: ..." — ne pas prefixer
    # nous-memes, sinon le client recoit "data: data: {...}" et JSON.parse echoue)
    yield {"comment": "ping"}

    # Envoyer le statut actuel
    async with lock:
        data = dict(cache["data"]) if cache["data"] else build_status(context)
    data["slow_endpoints"] = get_slow_endpoints()
    yield {"data": json.dumps(data)}

    # Heartbeats toutes les 15s avant fermeture (le client SSE se reconnecte avec retry: 5000)
    start = asyncio.get_event_loop().time()
    try:
        while True:
            await asyncio.sleep(15)
            if await request.is_disconnected():
                break
            if asyncio.get_event_loop().time() - start >= max_duration:
                break
            yield {"comment": "keep"}
    except asyncio.CancelledError:
        _logger.debug("Status stream cancelled")


@router.get("/api/status/stream")
async def status_stream(request: Request) -> EventSourceResponse:
    """Endpoint SSE pour le statut des services.

    Remplace le polling 5s de setInterval(pollStatus, 5000) : le client
    reçoit un ping initial + le statut, puis un heartbeat toutes les 15s.
    Le statut est lu depuis le cache côté serveur (rafraîchi par _status_refresher).
    Inclut retry: 5000 pour reconnexion automatique.
    """
    return EventSourceResponse(
        _status_generator(request),
        headers={"retry": "5000"},
    )
