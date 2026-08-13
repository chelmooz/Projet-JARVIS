"""StreamSink — Tampon thread-safe entre le pipeline (thread executor) et la réponse SSE.

Le pipeline JARVIS est synchrone et s'exécute dans un thread (executor
FastAPI) ; la réponse SSE vit dans l'event loop. ``StreamSink`` relie les deux :
- le thread de génération pousse chaque token (``push``) puis ``finish`` ;
- le générateur asynchrone ``events()`` livre les tokens au client.forward
  puis un dernier événement ``done`` portant le résultat complet.

Aucune dépendance à l'event loop (polling SimpleQueue, 20 ms) — reste simple
et déterministe hors boucle (pré-déploiement : aucun serveur réel).
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from collections.abc import AsyncIterator
from typing import Any

_logger = logging.getLogger("jarvis.streaming")

_POLL_DELAY = 0.02  # 20 ms : latence de relais des tokens vers le client


class StreamSink:
    """Tampon thread-safe des tokens d'une génération LLM en cours."""

    def __init__(self) -> None:
        self._tokens: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._done = threading.Event()
        self._final: dict[str, Any] = {}
        self._lock = threading.Lock()

    def push(self, token: str) -> None:
        """Pousse un token depuis le thread générateur (non bloquant)."""
        if token:
            self._tokens.put(token)

    def finish(self, payload: dict[str, Any] | None = None) -> None:
        """Marque la fin de la génération ; le payload final est livré en dernier."""
        if payload is not None:
            with self._lock:
                self._final.update(payload)
        self._done.set()

    def count(self) -> int:
        """Nombre de tokens actuellement en tampon (statistiques/tests)."""
        return self._tokens.qsize()

    def drain(self) -> list[str]:
        """Vide le tampon (usage tests/outils, jamais par events())."""
        out: list[str] = []
        while True:
            try:
                out.append(self._tokens.get_nowait())
            except queue.Empty:
                return out

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Génère les événements SSE : ``token`` puis ``done``.

        Chaque événement est un dict ``{"event": ..., "data": {...}}``.
        """
        while True:
            exhausted = self._done.is_set()
            while True:
                try:
                    token = self._tokens.get_nowait()
                except queue.Empty:
                    break
                yield {"event": "token", "data": {"token": token}}
            if exhausted:
                break
            await asyncio.sleep(_POLL_DELAY)

        with self._lock:
            final = dict(self._final)
        yield {"event": "done", "data": final}


__all__ = ["StreamSink"]
