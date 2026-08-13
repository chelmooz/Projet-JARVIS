"""Service de diagnostic externe — exécution d'outils portables (smartctl, Sysinternals).

Réexporte les composants principaux pour une importation simplifiée :
  from services.diagnostic_ext import DiagnosticExtService, DiagnosticExtError
"""

from __future__ import annotations

from services.diagnostic_ext.exceptions import DiagnosticExtError
from services.diagnostic_ext.service import DiagnosticExtService

__all__ = ["DiagnosticExtService", "DiagnosticExtError"]
