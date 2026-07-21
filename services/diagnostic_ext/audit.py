"""Journalisation des actions (audit log ISO 15489)."""

from __future__ import annotations

import contextlib
from typing import Any


def audit_log(log_service: Any | None, level: str, message: str) -> None:
    """Enregistre un message d'audit de manière sécurisée (fail-safe).

    Utilise ``contextlib.suppress`` pour garantir qu'une défaillance du
    service de journalisation ne propage pas d'exception à l'appelant.

    Args:
        log_service: Service de log (doit implémenter ``log(level, message)``).
        level: Niveau de log (ex: "INFO", "WARN", "ERROR").
        message: Message à journaliser.
    """
    if log_service is not None:
        with contextlib.suppress(Exception):
            log_service.log(level, message)


__all__ = ["audit_log"]
