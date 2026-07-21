"""Port — Interface structurelle pour le moteur de pipelines.

Sous-module séparé car ``services/pipeline.py`` importe explicitement
``from ports.pipeline import PipelinePort`` (et non depuis ``ports/__init__.py``).

NOTE : ``Pipeline`` est importé depuis ``models/`` — couplage ports→models.
Cible future : définir ``Pipeline`` dans ``ports/`` ou ``models/dto.py``.
Les dicts de retour (``list``, ``run``) et le contexte sont typés ici comme
``dict[str, Any]``. Cible future : TypedDict ou dataclasses dédiées.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from models import Pipeline  # Couplage ports→models : Pipeline est un DTO partagé.


@runtime_checkable
class PipelinePort(Protocol):
    """Contrat pour services/pipeline.py (PipelineEngine)."""

    def register(self, pipeline: Pipeline) -> None: ...
    def list(self) -> list[dict[str, Any]]: ...
    def get(self, pipeline_id: str) -> Pipeline | None: ...
    def run(
        self,
        pipeline_id: str,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


__all__ = ["PipelinePort"]
