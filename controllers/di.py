"""Dependency Injection — Composition Root de l'application JARVIS.

Responsabilité unique :
- Instancier tous les services (singletons).
- Exposer AppContext comme point d'entrée unique pour les contrôleurs.
- Garantir l'injection de dépendances (DIP) via des ports (ports/*).
"""
from __future__ import annotations

import logging
from typing import Any

from agents.factory import create_agents
from agents.supervisor import AgentSupervisor
from config.constants import DEFAULT_MODEL
from controllers.responses import ok, fail
from graph.agent_graph import AgentGraph
from ports import (
    AnalyticsPort,
    ChatPort,
    ConversationPort,
    EmbeddingPort,
    HabitPort,
    LogPort,
    MetricsPort,
    ModelRegistryPort,
    MultimodalPort,
    VectorPort,
)
from services.analytics import AnalyticsService
from services.conversation import ConversationService
from services.inference import InferenceService
from services.log import LogService
from services.memory import MemoryService
from services.metrics import MetricsService
from services.orchestrator import OrchestratorService
from services.pipeline import PipelineService
from services.selector import select_model, select_vision_model
from services.vector import VectorService

_logger = logging.getLogger("jarvis.di")


class _RouterService:
    """Routeur d'agents (sélectionne l'agent cible selon la tâche)."""
    
    def select_agent(self, task: str) -> str:
        """Sélectionne l'agent cible (logique simplifiée : toujours 'dev' par défaut)."""
        # TODO: implémenter la vraie logique de routing (keywords, regex, etc.)
        return "dev"


class _Toolbox:
    """Toolbox (diagnostics + fichiers) — injectée dans les agents."""
    
    def describe_tools(self) -> str:
        """Description textuelle des outils disponibles pour le LLM."""
        return "Aucun outil externe configuré."
    
    def is_enabled(self) -> bool:
        """True si la toolbox est active."""
        return False
    
    def auto_execute(self, task: str) -> dict[str, Any]:
        """Exécution automatique d'outils (retourne {} si désactivé)."""
        return {}


class AppContext:
    """Contexte applicatif — singletons de tous les services.
    
    Initialisé une seule fois au démarrage (lifespan FastAPI).
    Tous les attributs sont typés par des ports (DIP).
    """
    
    def __init__(self) -> None:
        self.inference: InferenceService | None = None
        self.memory: MemoryService | None = None
        self.vector: VectorService | None = None
        self.agents: dict[str, Any] = {}
        self.orchestrator: OrchestratorService | None = None
        self.toolbox: _Toolbox | None = None
        self.router_svc: _RouterService | None = None
        self.conversations: ConversationService | None = None
        self.pipeline: PipelineService | None = None
        self.metrics: MetricsService | None = None
        self.log: LogService | None = None
        self.analytics: AnalyticsService | None = None
        self.agent_supervisor: AgentSupervisor | None = None
        self._is_initialized = False
    
    def initialize(self) -> None:
        """Initialise tous les services (idempotent)."""
        if self._is_initialized:
            return
        
        self._do_initialize()
        self._is_initialized = True
        _logger.info("AppContext initialisé avec succès.")
    
    def _do_initialize(self) -> None:
        """Instanciation et câblage de tous les services."""
        # 1. Services de base (pas de dépendances)
        self.log = LogService()
        self.metrics = MetricsService()
        self.analytics = AnalyticsService()
        self.conversations = ConversationService()
        self.memory = MemoryService()
        
        # 2. Inférence (dépend de rien)
        self.inference = InferenceService()
        
        # 3. Vector store (dépend de inference)
        self.vector = VectorService(inference_service=self.inference)
        
        # 4. Toolbox (stateless)
        self.toolbox = _Toolbox()
        
        # 5. Routeur (stateless)
        self.router_svc = _RouterService()
        
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
            agent_runner=None,  # TODO: câbler si nécessaire
            inference=self.inference,
            memory=self.memory,
            model_selector=select_model,
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
