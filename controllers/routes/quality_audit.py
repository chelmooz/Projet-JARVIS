"""Route API — Audit Qualité : inspection complète du projet."""

from __future__ import annotations

import threading

from fastapi import APIRouter, Depends

from controllers.responses import fail, ok
from services.analysis import QualityAuditor

router = APIRouter()

_audit_lock = threading.Lock()


def get_auditor() -> QualityAuditor:
    """Dépendance : fournit une instance de l'auditeur qualité."""
    return QualityAuditor()


def _execute_audit(auditor: QualityAuditor):
    """Exécute l'audit avec un verrou non-bloquant."""
    if not _audit_lock.acquire(blocking=False):
        return fail("Audit déjà en cours", status_code=409)
    try:
        report = auditor.audit()
        report["success"] = True
        return ok(report)
    finally:
        _audit_lock.release()


@router.get("/api/quality-audit")
def run_audit(auditor: QualityAuditor = Depends(get_auditor)):
    """Compat: audit complet du projet via GET."""
    return _execute_audit(auditor)


@router.post("/api/quality-audit")
def run_audit_post(auditor: QualityAuditor = Depends(get_auditor)):
    """Audit complet du projet : code quality, tests, structure, documentation."""
    return _execute_audit(auditor)


__all__ = ["router"]
