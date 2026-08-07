"""LogAdapter — Adapte logging.Logger au callback (step, message, success).

Certaines fonctions du projet (ensure_venv, ensure_ollama_binary) sont
antérieures à l'usage de logging.Logger et attendent un simple callable
``log(step, message, success)``. Ce module fait le pont, en un seul
endroit, pour éviter que chaque appelant ne réinvente l'adaptation
(source du bug "'Logger' object is not callable").

Responsabilité unique : traduire un événement (step, message, success)
en appel logging.Logger. Rien d'autre.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

StepLogFn = Callable[[str, str, "bool | None"], None]


def to_step_logger(logger: logging.Logger) -> StepLogFn:
    """Construit un callback (step, message, success) délégant à ``logger``.

    Args:
        logger: Le logger destinataire des messages.

    Returns:
        Un callable compatible avec la signature attendue par
        ensure_venv() et ensure_ollama_binary().
    """

    def _log(step: str, message: str, success: bool | None = None) -> None:
        if success is False:
            logger.error("[%s] %s", step, message)
        else:
            logger.info("[%s] %s", step, message)

    return _log


__all__ = ["to_step_logger", "StepLogFn"]
