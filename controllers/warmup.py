"""Warmup & Lifecycle — Gestion propre du démarrage et de l'arrêt de l'application.

Refacto DevOps / SOLID / Async :
- Plus d'appels à ``get_context()`` global. Le contexte est récupéré via ``app.state``.
- Warmup critique SYNCHRONE : l'application n'accepte les requêtes qu'UNE FOIS les
  dépendances critiques (modèle par défaut, vector store) préchargées.
- Remplacement de ``threading.Thread`` par ``asyncio.to_thread`` pour une intégration
  propre avec l'event loop de FastAPI.
- Logging ERROR explicite en cas d'échec de préchauffage (fin du Fail-Silent).

Dettes signalées (non corrigées ici — fichiers tiers) :
- ``vector.consolidate`` et ``inference.close`` sont appelés mais ABSENTS des ports
  (``ports/``) → couplage à l'implémentation. À ajouter aux contrats VectorPort /
  InferencePort lors d'un passage dédié.
- ``_configure_root_logging`` est un symbole privé importé depuis ``services.log``.
- ``ctx.initialize()`` DOIT être idempotent (gérer son propre flag ``_is_initialized``) :
  c'est la responsabilité du contexte (di.py), pas du lifespan.
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
        # Délégation au thread pool pour ne pas bloquer l'event loop de démarrage.
        await asyncio.to_thread(vector.preload)
        await asyncio.to_thread(vector.consolidate)
        _logger.info("Consolidation vectorielle terminée avec succès.")
    except Exception as e:
        # Warmup tolérant : on ne lève pas (le reste de l'app démarre), mais le
        # niveau ERROR garantit la visibilité dans les logs de supervision.
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
        # Appel synchrone déporté dans un thread pour ne pas geler l'event loop.
        await asyncio.to_thread(inference.query, "Réponds 'ok' en un mot.", default_model)
        _logger.info("Warmup: modèle '%s' prêt et en cache.", default_model)
    except Exception as e:
        # Warmup tolérant : échec non bloquant, latence au premier appel réel.
        _logger.error(
            "ÉCHEC du warmup du modèle '%s' : %s. "
            "Les premières requêtes subiront une latence importante.", default_model, e,
        )


async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cycle de vie FastAPI : initialisation au démarrage, nettoyage à l'arrêt.

    Ce contexte garantit que l'application est pleinement opérationnelle
    avant d'accepter la première requête HTTP (principe de readiness).
    """
    # Imports locaux volontaires : le logging doit être configuré AVANT tout
    # import de module qui loggue (ordre d'initialisation). Pas de cycle.
    from services.diagnostics.checks import warn_low_memory
    from services.log import _configure_root_logging  # privé importé consciemment (docstring)

    # 1. Configuration initiale
    _configure_root_logging()
    warn_low_memory()

    # 2. Récupération du contexte.
    # L'injection dans app.state était prévue (cf. commentaire di.py : "Instance
    # globale injectée dans app.state par le lifespan") mais n'avait jamais été
    # écrite → l'app réelle plantait au démarrage (KeyError: 'context'). Corrigé :
    # on attache le singleton de di.py si ce n'est pas déjà fait (idempotent).
    # L'initialisation formelle (initialize()) reste déléguée à l'étape 3 ci-dessous.
    if not hasattr(app.state, "context"):
        from controllers.di import get_app_context  # import local : évite tout cycle d'import
        app.state.context = get_app_context()
    ctx = app.state.context

    # 3. Initialisation formelle du contexte.
    # Idempotence déléguée au contexte : ``initialize()`` gère son propre flag
    # ``_is_initialized`` (SRP). Le lifespan LIT l'état pour éviter une double-init
    # si le constructeur a déjà initialisé, mais n'ÉCRIT PAS l'interne du contexte.
    if hasattr(ctx, "initialize") and not getattr(ctx, "_is_initialized", False):
        ctx.initialize()

    _logger.info("=== Démarrage des services JARVIS ===")

    # 4. Warmup critique (synchrone du point de vue du démarrage de l'app).
    # L'app ne sera pas "ready" tant que ces tâches ne sont pas terminées.
    await _warmup_vector_store(ctx)
    await _warmup_default_model(ctx, DEFAULT_MODEL)

    # 5. Démarrage des tâches de fond (ex: file d'ingestion asynchrone).
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

    if ingest_queue is not None:
        ingest_queue.stop()
        _logger.info("File d'ingestion arrêtée.")

    # Signaler l'arrêt aux threads de fond (ex: status refresher).
    stop_event = getattr(ctx, "stop_event", None)
    if stop_event is not None:
        stop_event.set()

    # Fermeture propre des connexions HTTP (Ollama adapter).
    inference = getattr(ctx, "inference", None)
    if inference is not None:
        try:
            inference.close()
            _logger.info("Connexions d'inférence fermées proprement.")
        except Exception as e:
            # Shutdown best-effort : on logge, on ne propage pas.
            _logger.warning("Erreur lors de la fermeture de l'inférence : %s", e)

    _logger.info("=== Arrêt de JARVIS terminé ===")


__all__ = ["lifespan"]
