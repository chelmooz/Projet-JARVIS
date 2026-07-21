"""Route API — Audit Qualité : inspection complète du projet."""
import threading

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.analysis import QualityAuditor

router = APIRouter()
_auditor = QualityAuditor()
_audit_lock = threading.Lock()


@router.get("/api/quality-audit")
def run_audit():
    # Laisse sync : audit complet (lecture disque + analyse, I/O/CPU bloquant).
    """Compat: audit complet du projet via GET."""
    return run_audit_post()


@router.post("/api/quality-audit")
def run_audit_post():
    """Audit complet du projet : code quality, tests, structure, documentation."""
    if not _audit_lock.acquire(blocking=False):
        return JSONResponse(
            {"success": False, "error": "Audit deja en cours"},
            status_code=409,
        )
    try:
        report = _auditor.audit()
    finally:
        _audit_lock.release()
    report["success"] = True
    return report
