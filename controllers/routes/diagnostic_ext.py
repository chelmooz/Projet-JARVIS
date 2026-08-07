"""Routes API — Diagnostic externe (consentement des outils witr/psinfo/...).

Responsabilités :
- ``GET /api/diagnostic/consent`` : état actuel du consentement.
- ``POST /api/diagnostic/consent`` : accorder (True) ou retirer (False).

Le consentement est un fichier sur disque (``config/.diagnostic_consent``).
C'est un gate **d'usage local mono-utilisateur**, pas un contrôle d'accès
multi-utilisateur (cf. BACKLOG AUDIT.1 — dette technique assumée).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import ConsentRequest
from services.diagnostic_ext import DiagnosticExtService

router = APIRouter(tags=["diagnostic_ext"])


def _diag_ext_service() -> DiagnosticExtService:
    """Fabrique le service (point d'injection testable)."""
    return DiagnosticExtService()


@router.get("/api/diagnostic/consent")
def get_diagnostic_consent() -> dict:
    """Retourne l'état actuel du consentement diagnostic externe."""
    ok, _ = _diag_ext_service().ensure_consent()
    return {"consent_given": ok}


@router.post("/api/diagnostic/consent")
def set_diagnostic_consent(body: ConsentRequest) -> dict:
    """Accorde (``consent: True``) ou retire (``consent: False``) le consentement.

    La réponse reflète toujours l'**état réel** après l'opération
    (``ensure_consent`` relit le disque), jamais l'intention du client.
    """
    svc = _diag_ext_service()
    ok = svc.grant_consent() if body.consent else svc.revoke_consent()
    if not ok:
        raise HTTPException(status_code=500, detail="Échec de la modification du consentement")
    ok_state, _ = svc.ensure_consent()
    return {"consent_given": ok_state}


__all__ = ["router"]
