"""Ports — Contrats structurels (typing.Protocol) pour la couche adapter JARVIS.

Chaque port est une interface granulaire (ISP). Les adapters concrets
(OllamaAdapter, ShimmyAdapter, ...) implémentent un ou plusieurs ports.
Les services de la couche métier dépendent exclusivement de ces contrats.

NOTE : Les dicts de retour (get_metrics, search, get_habits, etc.) sont
typés ici comme ``dict[str, Any]``. Cible future : TypedDict ou dataclasses 
dédiées dans ``models/`` pour chaque contrat de retour, afin de renforcer 
le typage statique sans impacter la flexibilité actuelle.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from models import Result  # Couplage ports→models : Result est un DTO partagé.

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


# ---------------------------------------------------------------------------
# Logging & Metrics
# ---------------------------------------------------------------------------

@runtime_checkable
class LogPort(Protocol):
    """Contrat pour services/log.py (LogService)."""

    def log(self, level: LogLevel, message: str) -> None: ...


@runtime_checkable
class MetricsPort(Protocol):
    """Contrat pour services/metrics.py (MetricsService)."""

    def incr_requests(self, endpoint: str = "/api/jarvis") -> None: ...
    def incr_pipeline_run(self) -> None: ...
    def incr_errors(self) -> None: ...
    def get_metrics(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Inference — découpé en interfaces granulaires (ISP)
# ---------------------------------------------------------------------------

@runtime_checkable
class ChatPort(Protocol):
    """Génération de texte : prompt simple et chat multi-tours."""

    def query(self, prompt: str, model: str, system: str | None = None) -> str: ...
    def chat(self, model: str, messages: list[dict[str, Any]]) -> Result: ...


@runtime_checkable
class MultimodalPort(Protocol):
    """Analyse d'images (llama3.2-vision, etc.)."""

    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict[str, Any]: ...


@runtime_checkable
class EmbeddingPort(Protocol):
    """Calcul d'embeddings vectoriels (nomic-embed-text, etc.)."""

    def embed(self, text: str, model: str | None = None) -> list[float]: ...


@runtime_checkable
class ModelRegistryPort(Protocol):
    """Découverte et disponibilité des modèles locaux."""

    def list_models(self) -> list[str]: ...
    def is_available(self, model: str) -> bool: ...
    def first_available(self) -> str | None: ...
    def get_active_backend(self) -> str: ...
    def ping(self) -> bool: ...


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------

@runtime_checkable
class VectorPort(Protocol):
    """Contrat pour services/vector.py (VectorService)."""

    def index(self, text: str, metadata: dict[str, Any] | None = None) -> None: ...
    def index_batch(self, documents: list[tuple[str, dict[str, Any] | None]]) -> None: ...
    def vectorize_pending(self) -> int: ...
    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]: ...
    def stats(self) -> dict[str, Any]: ...
    def preload(self) -> None: ...
    def is_healthy(self) -> bool: ...


# ---------------------------------------------------------------------------
# Memory (habitudes utilisateur)
# ---------------------------------------------------------------------------

@runtime_checkable
class HabitPort(Protocol):
    """Contrat pour services/memory.py (MemoryService) — habitudes utilisateur."""

    def get_habits(self, limit: int = 10) -> list[dict[str, Any]]: ...
    def update_habits(self, entry: dict[str, Any]) -> None: ...
    def is_healthy(self) -> bool: ...


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@runtime_checkable
class AnalyticsPort(Protocol):
    """Contrat pour services/analytics.py (AnalyticsService)."""

    def track_query(
        self,
        agent: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> None: ...
    def get_stats(self) -> dict[str, Any]: ...
    def get_most_used(self) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@runtime_checkable
class ConversationPort(Protocol):
    """Contrat pour services/conversation.py (ConversationService)."""

    def create(self, title: str = "Nouvelle conversation") -> str: ...
    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        agent: str | None = None,
        model: str | None = None,
        backend: str | None = None,
    ) -> None: ...
    def get_conversation(self, conv_id: str) -> dict[str, Any] | None: ...
    def list_all(self) -> list[dict[str, Any]]: ...
    def delete(self, conv_id: str) -> None: ...
    def delete_all(self) -> None: ...
    def is_healthy(self) -> bool: ...


# ---------------------------------------------------------------------------
# File access (autorisation granulaire par dossier)
# NOTE : Nommé FilePort pour compat. Cible : FileAccessPort pour refléter
# que c'est un port d'autorisation, pas de lecture/écriture directe.
# ---------------------------------------------------------------------------

@runtime_checkable
class FilePort(Protocol):
    """Contrat pour le contrôle d'accès aux fichiers locaux."""

    def authorize(self, path: str) -> bool: ...
    def is_authorized(self, path: str) -> bool: ...
    def list_authorized(self) -> list[str]: ...
    def revoke(self, path: str) -> None: ...


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "LogLevel",
    "LogPort",
    "MetricsPort",
    "ChatPort",
    "MultimodalPort",
    "EmbeddingPort",
    "ModelRegistryPort",
    "VectorPort",
    "HabitPort",
    "AnalyticsPort",
    "ConversationPort",
    "FilePort",
]
