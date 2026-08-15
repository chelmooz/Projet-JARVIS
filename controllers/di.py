"""Dependency Injection — Composition Root de l'application JARVIS.

Responsabilité unique :
- Instancier tous les services (singletons).
- Exposer AppContext comme point d'entrée unique pour les contrôleurs.
- Garantir l'injection de dépendances (DIP) via des ports (ports/*).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.base import BaseAgent
from agents.factory import create_agents
from agents.supervisor import AgentSupervisor
from config.paths import CONFIG_DIR
from graph.agent_graph import AgentGraph
from services.analytics import AnalyticsService
from services.conversation import ConversationService
from services.file_system import FileSystemService
from services.inference import InferenceService
from services.log import LogService
from services.memory import MemoryService
from services.metrics import MetricsService
from services.orchestrator import OrchestratorService
from services.pipeline import PipelineService
from services.router import AgentRouter
from services.selector import select_model, select_vision_model
from services.toolbox import Toolbox
from services.vector import VectorService

_logger = logging.getLogger("jarvis.di")


class AppContext:
    """Contexte applicatif -- singletons de tous les services.

    Initialisé une seule fois au démarrage (lifespan FastAPI).
    Tous les attributs sont typés par des ports (DIP).
    """

    def __init__(self) -> None:
        self.inference: InferenceService | None = None
        self.memory: MemoryService | None = None
        self.vector: VectorService | None = None
        self.agents: dict[str, BaseAgent] = {}
        self.status_cache = {"ts": 0.0, "data": {}}
        self.profiles_path = str(CONFIG_DIR / "agent_profiles.json")
        self.orchestrator: OrchestratorService | None = None
        self.toolbox: Toolbox | None = None
        self.router_svc: AgentRouter | None = None
        self.conversations: ConversationService | None = None
        self.pipeline: PipelineService | None = None
        self.metrics: MetricsService | None = None
        self.log: LogService | None = None
        self.analytics: AnalyticsService | None = None
        self.agent_supervisor: AgentSupervisor | None = None
        self.file_system: FileSystemService | None = None
        self._initialized = False
        self._warmup_tasks: list[asyncio.Task[Any]] = []

    def initialize(self) -> None:
        """Initialise tous les services (idempotent)."""
        if self._initialized:
            return

        self._do_initialize()
        self._initialized = True
        _logger.info("AppContext initialisé avec succès.")

    def _do_initialize(self) -> None:
        """Instanciation et câblage de tous les services."""
        # 1. Services de base (pas de dépendances)
        self.log = LogService()
        self.metrics = MetricsService()
        self.analytics = AnalyticsService()
        self.conversations = ConversationService()
        self.memory = MemoryService()
        self.file_system = FileSystemService()

        # 2. Inférence (dépend de rien)
        self.inference = InferenceService()

        # 3. Vector store (dépend de inference)
        self.vector = VectorService(inference_service=self.inference)

        # 4. Toolbox (stateless — triggers chargés depuis toolbox_triggers.yaml)
        self.toolbox = Toolbox()

        # 5. Routeur (stateless — sélection d'agent par mots-clés/@mention)
        self.router_svc = AgentRouter()

        # 6. Agents (dépendent de inference, memory)
        self.agents = create_agents(
            inference_service=self.inference,
            memory_service=self.memory,
        )

        # 4.5 Injection de la toolbox dans les agents
        for agent in self.agents.values():
            agent.inject_toolbox(self.toolbox)

        # 4.6 Supervisor (garde-fou timeout)
        self.agent_supervisor = AgentSupervisor()

        # 7. Pipeline (dépend de inference, memory)
        self.pipeline = PipelineService(
            inference=self.inference,
            memory=self.memory,
            model_selector=select_model,
            agent_runner=lambda: self._build_agent_graph(),  # WRAPPER
        )

        # 5. Orchestrateur (Composition Root finale)
        self.orchestrator = OrchestratorService(
            inference=self.inference,
            memory=self.memory,
            vector=self.vector,
            log=self.log,
            analytics=self.analytics,
            conversations=self.conversations,
            metrics=self.metrics,
            agents=self.agents,
            router_service=self.router_svc,
            toolbox=self.toolbox,
            agent_graph_factory=self._build_agent_graph,
            vision_model_selector=select_vision_model,
        )

        _logger.info("Tous les services initialisés.")

    def _build_agent_graph(self) -> AgentGraph:
        """Factory nommée pour AgentGraph (closure sur self)."""
        assert self.inference is not None
        assert self.memory is not None
        assert self.vector is not None
        assert self.toolbox is not None
        assert self.router_svc is not None
        assert self.pipeline is not None
        assert self.conversations is not None
        assert self.agent_supervisor is not None
        return AgentGraph(
            model_provider=self.inference,
            memory=self.memory,
            vector_store=self.vector,
            toolbox=self.toolbox,
            agents=self.agents,
            router=self.router_svc,
            pipeline=self.pipeline,
            conversations=self.conversations,
            agent_supervisor=self.agent_supervisor,
        )


# Instance globale (injectée dans app.state par le lifespan)
_app_context = AppContext()


def get_app_context() -> AppContext:
    """Retourne l'instance globale du contexte applicatif."""
    return _app_context


__all__ = ["AppContext", "get_app_context"]
