"""Route API — Diagnostic machine hôte (GET /api/diag)."""

from __future__ import annotations

from fastapi import APIRouter

from services.diagnostic import DiagnosticService

router = APIRouter()


@router.get("/api/diag")
def get_diagnostic() -> dict:
    """Retourne le diagnostic complet de la machine hôte.

    Laisse sync : ``run_full()`` inspecte CPU/RAM/disque/réseau (I/O système bloquant).
    """
    return DiagnosticService().run_full()


__all__ = ["router"]
