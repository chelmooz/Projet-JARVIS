# Compat ascendante : DiagnosticService toujours accessible depuis
# from services.diagnostics import DiagnosticService
# from services.diagnostic import DiagnosticService (via facade)
from services.diagnostics.service import DiagnosticService

__all__ = ["DiagnosticService"]
