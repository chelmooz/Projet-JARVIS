"""Helpers de réponse JSON standardisée — format {data, error}.

Convention de migration graduelle :
  - ok(data)      → succès, enveloppe les données dans {"data": ..., "error": null}
  - fail(message) → erreur,  {"data": null, "error": "..."} avec le code HTTP donné

Les endpoints existants sont migrés petit à petit (sans casser l'API d'un coup).
"""

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any = None) -> dict[str, Any]:
    """Succès : enveloppe les données dans {data, error: null}."""
    return {"data": data, "error": None}


def fail(message: str, status_code: int = 400) -> JSONResponse:
    """Erreur : {data: null, error: message} avec le code HTTP donné."""
    return JSONResponse({"data": None, "error": message}, status_code=status_code)
