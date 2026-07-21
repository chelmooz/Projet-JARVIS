"""AppContext — Conteneur de services & Composition Root (DI).

Initialisation explicite dans build_app() (controllers.context).
Cette classe est le seul endroit autorisé à instancier les dépendances concrètes.
"""
import logging
import os
import threading

from config.constants import PROJECT_DIR, REFRESH_INTERVAL, WARMUP_DELAY

_logger = logging.getLogger("jarvis.di")


class AppContext:
    """Conteneur de tous les services métier.
    
    Applique le pattern Composition Root :
    - Aucune logique métier.
    - Instanciation explicite et Fail Fast des dépendances.
    - Pas de cycle d'import (imports locaux dans _do_initialize).
    """

    def __init__(self):
        self.inference = None
        self.memory = None
        self.vector = None
        self.log = None
        self.analytics = None
        self.conversations = None
        self.metrics = None
        self.agents = None
        self.router_svc = None
        self.toolbox = None
        self.orchestrator = None
        self.ingest_queue = None
        
        self.status_cache: dict = {"ts": 0, "data": {}}
        self.profiles_path: str = os.path.join(PROJECT_DIR, "config", "agent_profiles.json")
        self.init_report: dict[str, str] = {}
        self._initialized = False
        
        # Coordination threads
        self.stop_event = threading.Event()
        self.refresh_interval = REFRESH_INTERVAL
        self.warmup_delay = WARMUP_DELAY

    def initialize(self):
        """Initialise tous les services. Fail Fast en cas d'erreur."""
        if self._initialized:
            return
        self._initialized = True
        self._do_initialize()
        _logger.info("Tous les services ont été initialisés avec succès.")

    def _do_initialize(self):
        # Imports locaux pour éviter les cycles et respecter le DIP
        from agents.factory import create_agents
        from graph import AgentGraph
        from services.analytics import AnalyticsService
        from services.conversation import ConversationService
        from services.diagnostic_ext import DiagnosticExtService
        from services.file_system import FileSystemService
        from services.inference import InferenceService
        from services.ingest_queue import IngestQueue
        from services.log import LogService
        from services.memory import MemoryService
        from services.metrics import MetricsService
        from services.orchestrator import OrchestratorService
        from services.router import AgentRouter
        from services.toolbox import Toolbox
        from services.vector import VectorService

        self.init_report = {}

        # 1. Services de base (Fail Fast)
        self.inference = InferenceService()
        self.memory = MemoryService()
        self.vector = VectorService()
        self.log = LogService()
        self.analytics = AnalyticsService()
        self.conversations = ConversationService()
        self.metrics = MetricsService()
        self.router_svc = AgentRouter()
        
        self.init_report.update({
            "inference": "OK", "memory": "OK", "vector": "OK", "log": "OK",
            "analytics": "OK", "conversations": "OK", "metrics": "OK", "router_svc": "OK"
        })

        # 2. File d'ingestion (dépend de vector et conversations)
        self.ingest_queue = IngestQueue(self.vector)
        self.conversations.set_on_message(self.ingest_queue.enqueue)

        # 3. Agents (dépend de inference et memory)
        self.agents = create_agents(self.inference, self.memory)
        self.init_report["agents"] = "OK"

        # 4. Toolbox (dépend de services externes)
        self.toolbox = Toolbox(
            diagnostic_service=DiagnosticExtService(),
            file_service=FileSystemService(),
        )
        for agent in self.agents.values():
            agent.inject_toolbox(self.toolbox)
        self.init_report["toolbox"] = "OK"

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
            # DIP: Injection de la factory concrète pour AgentGraph
            agent_graph_factory=lambda: AgentGraph(
                model_provider=self.inference,
                memory=self.memory,
                vector_store=self.vector,
                toolbox=self.toolbox,
                agents=self.agents,
                router=self.router_svc,
                conversations=self.conversations,
            )
        )
        self.init_report["orchestrator"] = "OK"

    @property
    def ready(self) -> bool:
        return self.orchestrator is not None
