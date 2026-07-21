"""Compatibilité ascendante : réexport de DiagnosticService.

Permet les deux formes d'import :
  - ``from services.diagnostics import DiagnosticService``
  - ``from services.diagnostic import DiagnosticService`` (via façade)
"""

from __future__ import annotations

from services.diagnostics.service import DiagnosticService

__all__ = ["DiagnosticService"]
