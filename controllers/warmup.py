"""Warmup & Lifecycle — Gestion propre du démarrage et de l'arrêt de l'application.

Refacto DevOps / SOLID / Async :
- Plus d'appels à ``get_context()`` global. Le contexte est récupéré via ``app.state``.
- Warmup critique ASYNCHRONE : lancé en arrière-plan via ``asyncio.create_task`` pour
  ne pas bloquer le lifespan et permettre à l'app d'accepter des requêtes immédiatement.
- Remplacement de ``threading.Thread`` par ``asyncio.to_thread`` pour une intégration
  propre avec l'event loop de FastAPI.
- Logging ERROR explicite en cas d'échec de préchauffage (fin du Fail-Silent).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import logging

from fastapi import FastAPI

from config.constants import DEFAULT_MODEL

_logger = logging.getLogger("jarvis.warmup")


async def _warmup_vector_store(ctx) -> None:
    """Pré-charge et consolide le store vectoriel de manière asynchrone."""
    vector = getattr(ctx, "vector", None)
    if not vector:
        return

    try:
        _logger.info("Préchargement du store vectoriel en cours...")
        await asyncio.to_thread(vector.preload)
        await asyncio.to_thread(vector.consolidate)
        _logger.info("Consolidation vectorielle terminée avec succès.")
    except Exception as e:
        _logger.error(
            "ÉCHEC CRITIQUE du préchargement vectoriel : %s. "
            "La fonctionnalité RAG sera indisponible ou dégradée.", e,
        )


async def _warmup_default_model(ctx, default_model: str) -> None:
    """Envoie une requête de réveil au modèle par défaut pour éviter le cold-start."""
    inference = getattr(ctx, "inference", None)
    if not inference:
        return

    if not inference.is_available(default_model):
        _logger.warning(
            "Modèle par défaut '%s' non disponible. "
            "Le premier appel subira une latence de chargement.",
            default_model,
        )
        return

    try:
        _logger.info("Warmup: pré-chargement du modèle '%s' en mémoire...", default_model)
        await asyncio.to_thread(inference.query, "Réponds 'ok' en un mot.", default_model)
        _logger.info("Warmup: modèle '%s' prêt et en cache.", default_model)
    except Exception as e:
        _logger.error(
            "ÉCHEC du warmup du modèle '%s' : %s. "
            "Les premières requêtes subiront une latence importante.", default_model, e,
        )


async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cycle de vie FastAPI : initialisation au démarrage, nettoyage à l'arrêt."""
    from services.diagnostics.checks import warn_low_memory
    from services.log import _configure_root_logging

    _configure_root_logging()
    warn_low_memory()

    if not hasattr(app.state, "context"):
        from controllers.di import get_app_context
        app.state.context = get_app_context()
    ctx = app.state.context

    if hasattr(ctx, "initialize") and not getattr(ctx, "_is_initialized", False):
        ctx.initialize()

    _logger.info("=== Démarrage des services JARVIS ===")

    # CORRECTION : Warmup non-bloquant en arrière-plan.
    # On conserve la référence des tâches dans le contexte pour éviter le
    # garbage collection prématuré (piège classique asyncio).
    if not hasattr(ctx, "_warmup_tasks"):
        ctx._warmup_tasks = []
    
    task_vector = asyncio.create_task(_warmup_vector_store(ctx))
    ctx._warmup_tasks.append(task_vector)
    
    task_model = asyncio.create_task(_warmup_default_model(ctx, DEFAULT_MODEL))
    ctx._warmup_tasks.append(task_model)
    
    _logger.info("Warmup lancé en arrière-plan. L'application est prête à accepter des requêtes.")

    ingest_queue = getattr(ctx, "ingest_queue", None)
    if ingest_queue is not None:
        ingest_queue.start()
        _logger.info("File d'ingestion démarrée.")

    _logger.info("=== JARVIS est prêt à accepter des requêtes ===")

    yield  # L'application tourne ici et accepte le trafic.

    # ==========================================================================
    # SHUTDOWN (arrêt propre et déterministe)
    # ==========================================================================
    _logger.info("=== Arrêt de JARVIS en cours ===")

    # Annuler les tâches de warmup en cours si elles tournent encore
    for task in getattr(ctx, "_warmup_tasks", []):
        if not task.done():
            task.cancel()

    if ingest_queue is not None:
        ingest_queue.stop()
        _logger.info("File d'ingestion arrêtée.")

    stop_event = getattr(ctx, "stop_event", None)
    if stop_event is not None:
        stop_event.set()

    inference = getattr(ctx, "inference", None)
    if inference is not None:
        try:
            inference.close()
            _logger.info("Connexions d'inférence fermées proprement.")
        except Exception as e:
            _logger.warning("Erreur lors de la fermeture de l'inférence : %s", e)

    _logger.info("=== Arrêt de JARVIS terminé ===")


_warmup = lifespan  # Alias requis par test_context_refactor.py::test_warmup_module_exists

__all__ = ["lifespan", "_warmup", "_warmup_vector_store"]