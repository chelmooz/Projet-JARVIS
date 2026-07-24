"""Models — Entités métier et DTO (couche M)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class OnError(str, Enum):
    ABORT = "abort"
    SKIP = "skip"
    RETRY = "retry"


@dataclass(frozen=True)
class Result:
    success: bool
    data: dict[str, Any]
    agent: str
    model: str
    backend: str = "ollama"
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.success and not self.error:
            object.__setattr__(self, "error", "unknown error")
        if self.success and self.error:
            object.__setattr__(self, "error", None)

    @classmethod
    def ok(cls, data: dict[str, Any], agent: str, model: str, backend: str = "ollama") -> Result:
        return cls(success=True, data=data, agent=agent, model=model, backend=backend)

    @classmethod
    def fail(cls, error: str, agent: str = "unknown", model: str = "unknown", backend: str = "ollama") -> Result:
        return cls(success=False, data={}, agent=agent, model=model, backend=backend, error=error)

    @property
    def is_success(self) -> bool:
        return self.success


@dataclass(frozen=True)
class AgentProfile:
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


@dataclass
class Conversation:
    id: str
    title: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Conversation.id must not be empty")


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    agent: str = ""
    model: str = ""
    backend: str = "ollama"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant", "system"):
            raise ValueError(f"Invalid role: {self.role!r}")


@dataclass(frozen=True)
class Document:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("Document.text must not be empty")


@dataclass(frozen=True)
class PipeStep:
    name: str
    agent_key: str
    prompt_template: str
    on_error: OnError = OnError.ABORT

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("PipeStep.name must not be empty")


@dataclass(frozen=True)
class Pipeline:
    id: str
    steps: tuple[PipeStep, ...] = ()
    on_error: OnError = OnError.ABORT

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Pipeline.id must not be empty")


@dataclass(frozen=True)
class AgentInput:
    task: str = ""
    text: str | None = None
    image: str | None = None
    conversation_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    model: str | None = None

    def __post_init__(self) -> None:
        if self.text and not self.task:
            object.__setattr__(self, "task", self.text)
        if not self.task:
            raise ValueError("AgentInput.task must not be empty")


@dataclass(frozen=True)
class AgentOutput:
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
]
