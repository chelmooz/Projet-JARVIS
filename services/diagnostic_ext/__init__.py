"""Service de diagnostic externe — exécution d'outils portables (smartctl, Sysinternals)."""
from services.diagnostic_ext.exceptions import DiagnosticExtError
from services.diagnostic_ext.service import DiagnosticExtService

__all__ = ["DiagnosticExtService", "DiagnosticExtError"]
