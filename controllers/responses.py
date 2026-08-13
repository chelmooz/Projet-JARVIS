"""Helpers de réponse JSON standardisée — format {data, error}.

Convention de migration graduelle :
  - ``ok(data)``      → succès, enveloppe les données dans ``{"data": ..., "error": null}``
  - ``fail(message)`` → erreur, ``{"data": null, "error": "..."}`` avec le code HTTP donné

Les endpoints existants sont migrés petit à petit (sans casser l'API d'un coup).

Note d'implémentation :
  - ``ok`` retourne un ``dict`` (et non une ``JSONResponse``) pour laisser FastAPI
    sérialiser et appliquer d'éventuels ``response_model`` (validation Pydantic).
  - ``fail`` retourne une ``JSONResponse`` car il doit piloter le ``status_code``
    (un dict retourné serait toujours HTTP 200). ``status_code`` devrait être >= 400.
"""

from __future__ import annotations

from typing import Any, TypedDict

from fastapi.responses import JSONResponse


class Envelope(TypedDict):
    """Contrat de l'enveloppe de réponse JSON (single source of truth du format)."""

    data: Any
    error: str | None


def ok(data: Any = None) -> Envelope:
    """Succès : enveloppe les données dans ``{data, error: null}`` (HTTP 200)."""
    return {"data": data, "error": None}


def fail(message: str, status_code: int = 400) -> JSONResponse:
    """Erreur : ``{data: null, error: message}`` avec le code HTTP donné (>= 400)."""
    body: Envelope = {"data": None, "error": message}
    return JSONResponse(body, status_code=status_code)


__all__ = ["ok", "fail", "Envelope"]
