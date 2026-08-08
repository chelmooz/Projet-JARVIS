"""Routes API — Diagnostic externe (consentement retiré, API de compat).

Responsabilités :
- ``GET /api/diagnostic/consent`` : renvoie toujours ``consent_given: true``.
- ``POST /api/diagnostic/consent`` : no-op (retourne ``true`` aussi).

C1 — le consentement a été retiré (usage mono-utilisateur, clé USB) : aucun
fichier, aucune permission, l'exécution des outils est directe. Les endpoints
sont conservés pour la compatibilité des clients existants (frontend ancien).
"""
from __future__ import annotations

from fastapi import APIRouter

from models.schemas import ConsentRequest

router = APIRouter(tags=["diagnostic_ext"])


@router.get("/api/diagnostic/consent")
def get_diagnostic_consent() -> dict:
    """Retourne l'état du consentement : toujours accordé (C1)."""
    return {"consent_given": True}


@router.post("/api/diagnostic/consent")
def set_diagnostic_consent(body: ConsentRequest) -> dict:
    """No-op de compatibilité : le consentement est permanent (C1)."""
    return {"consent_given": True}


__all__ = ["router"]
