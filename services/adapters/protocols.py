"""Ports (Protocols) pour l'architecture ports-and-adapters.

Ce module définit les interfaces que le code métier utilise,
sans connaître les implémentations concrètes.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from models import Result


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
    status: str = ""


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

    def query(self, prompt: str, model: str, system: str | None = None) -> str:
        """Envoie un prompt au modèle et retourne la réponse brute."""
        ...

    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict[str, Any]:
        """Envoie un prompt multimodal (texte + image) au modèle."""
        ...

    def chat(self, model: str, messages: list[dict[str, Any]]) -> Result:
        """Envoie une conversation structurée (historique de messages)."""
        ...

    def is_available(self, model: str) -> bool:
        """Vérifie si un modèle est disponible sur le backend actif."""
        ...

    def first_available(self) -> str | None:
        """Retourne le premier modèle disponible sur le backend actif."""
        ...

    def list_models(self) -> list[str]:
        """Retourne les modèles disponibles sur le backend actif."""
        ...

    def resolve_model(self, model: str) -> str | None:
        """Résout un nom court de config vers le tag Ollama réel (None si absent)."""
        ...

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Génère un embedding vectoriel pour le texte donné."""
        ...

    def get_active_backend(self) -> str:
        """Retourne le nom du backend actif."""
        ...

    def ping(self) -> bool:
        """Vérifie si le backend Ollama est accessible."""
        ...

    def close(self) -> None:
        """Libère l'adaptateur (fermeture déterministe du client HTTP à l'arrêt)."""
        ...


class IResponseJudge(Protocol):
    """Port pour le juge isolé (Verifier Sub-Agent).

    Respecte SKILL.md §6 : le juge ne voit PAS le raisonnement de l'acteur.
    Il évalue uniquement : requête + chunks + réponse finale.
    """

    def evaluate(self, query: str, chunks: list[str], response: str) -> dict[str, Any]:
        """Évalue la qualité d'une réponse.

        Retourne un dict structuré :
        - score: float (0.0 à 1.0)
        - reason: str (justification concise)

        Lève JudgeParseError si le JSON est invalide ou incomplet.
        """
        ...
