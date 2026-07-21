"""Models — Entités métier et DTO (couche M).

Chaque dataclass est une valeur immuable ou une entité identifiée.
Les invariants sont validés dans ``__post_init__``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OnError(str, Enum):
    """Stratégie de gestion d'erreur dans un pipeline."""

    ABORT = "abort"
    SKIP = "skip"
    RETRY = "retry"


# ---------------------------------------------------------------------------
# Résultat d'inférence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Result:
    """Résultat immuable d'un appel d'inférence.

    Invariant : ``success=False`` implique ``error`` non-vide.
    """

    success: bool
    data: dict[str, Any]
    agent: str
    model: str
    backend: str = "ollama"
    error: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self) -> None:
        if not self.success and not self.error:
            object.__setattr__(self, "error", "unknown error")
        if self.success and self.error:
            object.__setattr__(self, "error", None)

    @classmethod
    def ok(
        cls,
        data: dict[str, Any],
        agent: str,
        model: str,
        backend: str = "ollama",
    ) -> Result:
        return cls(
            success=True, data=data, agent=agent, model=model, backend=backend,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        agent: str = "unknown",
        model: str = "unknown",
        backend: str = "ollama",
    ) -> Result:
        return cls(
            success=False, data={}, agent=agent, model=model,
            backend=backend, error=error,
        )

    @property
    def is_success(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentProfile:
    """Profil statique d'un agent (config, pas d'état runtime)."""

    key: str
    name: str
    title: str
    model: str
    system_prompt: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("AgentProfile.key must not be empty")
        if not self.model:
            raise ValueError("AgentProfile.model must not be empty")


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@dataclass
class Conversation:
    """Conversation persistante identifiée par id."""

    id: str
    title: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Conversation.id must not be empty")


@dataclass(frozen=True)
class Message:
    """Message immuable au sein d'une conversation."""

    role: str
    content: str
    agent: str = ""
    model: str = ""
    backend: str = "ollama"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {self.role!r}")


# ---------------------------------------------------------------------------
# Documents & Recherche vectorielle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Document:
    """Document indexé pour la recherche vectorielle."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("Document.text must not be empty")


# ---------------------------------------------------------------------------
# Pipeline (orchestration séquentielle)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PipeStep:
    """Étape élémentaire d'un pipeline."""

    name: str
    agent_key: str
    prompt_template: str
    on_error: OnError = OnError.ABORT

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PipeStep.name must not be empty")
        if not self.agent_key:
            raise ValueError("PipeStep.agent_key must not be empty")


@dataclass(frozen=True)
class Pipeline:
    """Pipeline séquentiel d'étapes agentiques."""

    id: str
    steps: tuple[PipeStep, ...] = ()
    on_error: OnError = OnError.ABORT

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Pipeline.id must not be empty")


# ---------------------------------------------------------------------------
# DTO Entrée / Sortie (API ↔ Services)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentInput:
    """DTO d'entrée : requête utilisateur vers un agent.

    Remplace l'ancien Task (fusion KISS).
    Le champ ``text`` est un alias legacy conservé pour compatibilité
    avec les tests existants (test_agent_router.py).
    """

    task: str = ""
    text: str | None = None
    image: str | None = None
    conversation_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    model: str | None = None

    def __post_init__(self) -> None:
        # Compat legacy : si text est fourni et task est vide, utiliser text.
        if self.text and not self.task:
            object.__setattr__(self, "task", self.text)
        if not self.task:
            raise ValueError("AgentInput.task must not be empty")


@dataclass(frozen=True)
class AgentOutput:
    """DTO de sortie : réponse d'un agent vers l'API."""

    response: str
    agent: str
    model: str
    backend: str = "ollama"
    suggested_skill: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Compat ascendante (deprecated — utiliser AgentInput directement)
# ---------------------------------------------------------------------------
Task = AgentInput


__all__ = [
    "OnError",
    "Result",
    "AgentProfile",
    "Conversation",
    "Message",
    "Document",
    "PipeStep",
    "Pipeline",
    "AgentInput",
    "AgentOutput",
    "Task",
]"""Models — Entités métier et DTO (couche M).

Chaque dataclass est une valeur immuable ou une entité identifiée.
Les invariants sont validés dans ``__post_init__``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OnError(str, Enum):
    """Stratégie de gestion d'erreur dans un pipeline."""

    ABORT = "abort"
    SKIP = "skip"
    RETRY = "retry"


# ---------------------------------------------------------------------------
# Résultat d'inférence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Result:
    """Résultat immuable d'un appel d'inférence.

    Invariant : ``success=False`` implique ``error`` non-vide.
    """

    success: bool
    data: dict[str, Any]
    agent: str
    model: str
    backend: str = "ollama"
    error: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self) -> None:
        if not self.success and not self.error:
            object.__setattr__(self, "error", "unknown error")
        if self.success and self.error:
            object.__setattr__(self, "error", None)

    @classmethod
    def ok(
        cls,
        data: dict[str, Any],
        agent: str,
        model: str,
        backend: str = "ollama",
    ) -> Result:
        return cls(
            success=True, data=data, agent=agent, model=model, backend=backend,
        )

    @classmethod
    def fail(
        cls,
        error: str,
        agent: str = "unknown",
        model: str = "unknown",
        backend: str = "ollama",
    ) -> Result:
        return cls(
            success=False, data={}, agent=agent, model=model,
            backend=backend, error=error,
        )

    @property
    def is_success(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentProfile:
    """Profil statique d'un agent (config, pas d'état runtime)."""

    key: str
    name: str
    title: str
    model: str
    system_prompt: str = ""

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("AgentProfile.key must not be empty")
        if not self.model:
            raise ValueError("AgentProfile.model must not be empty")


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@dataclass
class Conversation:
    """Conversation persistante identifiée par id."""

    id: str
    title: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Conversation.id must not be empty")


@dataclass(frozen=True)
class Message:
    """Message immuable au sein d'une conversation."""

    role: str
    content: str
    agent: str = ""
    model: str = ""
    backend: str = "ollama"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {self.role!r}")


# ---------------------------------------------------------------------------
# Documents & Recherche vectorielle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Document:
    """Document indexé pour la recherche vectorielle."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("Document.text must not be empty")


# ---------------------------------------------------------------------------
# Pipeline (orchestration séquentielle)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PipeStep:
    """Étape élémentaire d'un pipeline."""

    name: str
    agent_key: str
    prompt_template: str
    on_error: OnError = OnError.ABORT

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PipeStep.name must not be empty")
        if not self.agent_key:
            raise ValueError("PipeStep.agent_key must not be empty")


@dataclass(frozen=True)
class Pipeline:
    """Pipeline séquentiel d'étapes agentiques."""

    id: str
    steps: tuple[PipeStep, ...] = ()
    on_error: OnError = OnError.ABORT

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Pipeline.id must not be empty")


# ---------------------------------------------------------------------------
# DTO Entrée / Sortie (API ↔ Services)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentInput:
    """DTO d'entrée : requête utilisateur vers un agent.

    Remplace l'ancien Task (fusion KISS).
    """

    task: str
    image: str | None = None
    conversation_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    model: str | None = None

    def __post_init__(self) -> None:
        if not self.task:
            raise ValueError("AgentInput.task must not be empty")


@dataclass(frozen=True)
class AgentOutput:
    """DTO de sortie : réponse d'un agent vers l'API."""

    response: str
    agent: str
    model: str
    backend: str = "ollama"
    suggested_skill: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Compat ascendante (deprecated — utiliser AgentInput directement)
# ---------------------------------------------------------------------------
Task = AgentInput  # Alias legacy pour tests/test_router.py et services/router.py


__all__ = [
    "OnError",
    "Result",
    "AgentProfile",
    "Conversation",
    "Message",
    "Document",
    "PipeStep",
    "Pipeline",
    "AgentInput",
    "AgentOutput",
    "Task",
]
