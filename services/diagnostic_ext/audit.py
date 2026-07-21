"""Journalisation des actions (audit log ISO 15489)."""
import contextlib


def audit_log(log_service, level: str, message: str):
    if log_service:
        with contextlib.suppress(Exception):
            log_service.log(level, message)
