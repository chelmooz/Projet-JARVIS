"""Route API — Diagnostic machine hôte (GET /api/diag)."""
from fastapi import APIRouter

from services.diagnostic import DiagnosticService

router = APIRouter()


@router.get("/api/diag")
def get_diagnostic():
    # Laisse sync : run_full() inspecte CPU/RAM/disque/réseau (I/O système bloquant).
    """Retourne le diagnostic complet de la machine hôte."""
    d = DiagnosticService()
    return d.run_full()
