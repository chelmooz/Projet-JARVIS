"""Warmup asynchrone (hors event loop) + cycle de vie FastAPI.

Les dependances sont passees via AppContext pour eviter l'import circulaire
avec controllers.context.
"""

import logging
import threading
import time

from config.constants import DEFAULT_MODEL
from controllers.di import AppContext
from controllers.status import _refresh_status_cache, _status_refresher

_logger = logging.getLogger("jarvis.context")


def _warmup_vector_store(ctx: AppContext):
    """Pre-charge et consolide le store vectoriel (best-effort, hors ligne)."""
    vector = ctx.vector
    log = ctx.log
    try:
        vector.preload()
    except Exception as e:
        log.log("WARN", f"Preload vectoriel: echec ({e})")
    try:
        vector.consolidate()
        log.log("INFO", "Consolidation vectorielle terminee")
    except Exception as e:
        log.log("WARN", f"Consolidation vectorielle: echec ({e})")


def _warmup_default_model(ctx: AppContext, default_model: str):
    """Envoie une requete de reveil au modele par defaut si disponible."""
    inference = ctx.inference
    log = ctx.log
    if not inference.is_available(default_model):
        return
    try:
        log.log("INFO", f"Warmup: pre-chargement du modele {default_model}...")
        inference.query("Reponds 'ok' en un mot.", default_model)
        log.log("INFO", "Warmup: modele pret.")
    except Exception as e:
        log.log("WARN", f"Warmup: echec ({e})")


def _warmup(ctx: AppContext):
    """Thread de pre-chargement asynchrone (hors event loop).

    Apres le delai de warmup : rafraichit le cache de status, lance le refresher
    periodique, puis pre-charge le store vectoriel et le modele par defaut.
    """
    # time.sleep correct ici : hors event loop (thread lance via threading.Thread)
    time.sleep(ctx.warmup_delay)
    default_model = DEFAULT_MODEL
    _refresh_status_cache(ctx, ctx.cache_lock)
    threading.Thread(
        target=_status_refresher, args=(ctx, ctx.stop_event, ctx.refresh_interval), daemon=True
    ).start()
    log = ctx.log
    log.log("INFO", "Cache status rafraichi (warmup)")
    _warmup_vector_store(ctx)
    _warmup_default_model(ctx, default_model)


async def lifespan(app):
    """Cycle de vie FastAPI : lance le warmup au demarrage, arret propre a la sortie."""
    from services.diagnostics.checks import warn_low_memory
    from services.log import _configure_root_logging

    _configure_root_logging()
    warn_low_memory()

    from controllers.context import get_context
    ctx = get_context()
    threading.Thread(target=_warmup, args=(ctx,), daemon=True).start()
    ingest_queue = getattr(ctx, "ingest_queue", None)
    if ingest_queue is not None:
        ingest_queue.start()
    yield
    if ingest_queue is not None:
        ingest_queue.stop()
    ctx.stop_event.set()
    inference = ctx.inference
    if inference is not None:
        inference.close()
    log = ctx.log
    log.log("INFO", "Warmup: arret propre signale.")
