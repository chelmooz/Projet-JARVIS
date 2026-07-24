"""Ports (Protocols) pour l'architecture ports-and-adapters.

Ce module définit les interfaces que le code métier utilise,
sans connaître les implémentations concrètes.
"""

from typing import Protocol, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class TraceRecord:
    """DTO pur pour la trace d'un pipeline.

    Aucune logique métier — uniquement des données.
    """
    trace_id: str
    pipeline_id: str
    query: str
    retrieved_chunk_ids: list[str]
    judge_score: float
    judge_reason: str
    timestamp: str = ""
    feedback: str | None = None


class ITraceStore(Protocol):
    """Port pour la persistance des traces (sidecar JSONL)."""

    def append(self, record: TraceRecord) -> None:
        """Ajoute une trace au store."""
        ...


class IVectorSearch(Protocol):
    """Port pour la recherche vectorielle (RAG)."""

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Recherche les chunks les plus similaires à la requête.

        Retourne une liste de dicts avec au minimum :
        - id: str (chunk_id)
        - text: str (contenu du chunk)
        - score: float (similarité cosine)
        """
        ...


class LLMAdapter(Protocol):
    """Port pour l'adaptateur de modèle de langage (Ollama, etc.)."""

    def query(self, prompt: str, model: str) -> Any:
        """Envoie un prompt au modèle et retourne la réponse brute."""
        ...