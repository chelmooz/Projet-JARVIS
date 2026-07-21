"""Façade de compatibilité ascendante — redirige vers services/diagnostics/service.py.
Utilisation conservée :
  from services.diagnostic import DiagnosticService
  diag = DiagnosticService()
  rapport = diag.run_full()
  diag.print_report()
"""
from services.diagnostics.service import DiagnosticService  # noqa: F401
