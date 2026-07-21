"""Models — Dataclasses pures (couche M de MVC)"""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Result:
    success: bool
    data: dict
    agent: str
    model: str
    backend: str = "ollama"
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def ok(cls, data: dict, agent: str, model: str, backend: str = "ollama") -> "Result":
        return cls(success=True, data=data, agent=agent, model=model, backend=backend)

    @classmethod
    def fail(cls, error: str, agent: str = "unknown", model: str = "unknown") -> "Result":
        return cls(success=False, data={}, agent=agent, model=model, error=error)


@dataclass
class Task:
    text: str
    image: str | None = None
    conversation_id: str | None = None


@dataclass
class AgentProfile:
    key: str
    name: str
    title: str
    model: str
    system_prompt: str = ""


@dataclass
class Conversation:
    id: str
    title: str = ""
    created_at: float = 0.0


@dataclass
class Message:
    role: str
    content: str
    agent: str = ""
    model: str = ""
    backend: str = "ollama"


@dataclass
class Document:
    text: str
    metadata: dict | None = None
    score: float = 0.0


# ─── Entités métier (SOLID.md Sprint 1) ──────────────────────────────

@dataclass
class PipeStep:
    name: str
    agent_key: str
    prompt_template: str
    on_error: str = "abort"


@dataclass
class Pipeline:
    id: str
    steps: list[PipeStep]
    on_error: str = "abort"


# ─── DTO Agents (Sprint 2) ────────────────────────────────────────────

@dataclass
class AgentInput:
    task: str
    image: str | None = None
    context: dict | None = None
    model: str | None = None


@dataclass
class AgentOutput:
    response: str
    agent: str
    model: str
    backend: str = "ollama"
    suggested_skill: str | None = None
    error: str | None = None
    metadata: dict | None = None


__all__ = [
    "Result", "Task", "AgentProfile", "Conversation", "Message", "Document",
    "PipeStep", "Pipeline",
    "AgentInput", "AgentOutput",
]
