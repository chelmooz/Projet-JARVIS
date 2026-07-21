"""AppContext — conteneur de services + injection de dependances (DI).

Initialisation explicite dans build_app() (controllers.context), pas a l'import.
Les singletons module-level (controllers.context) sont mis a jour apres init via
_sync_module_globals(). Cette classe ne depend pas de controllers.context (pas de
cycle d'import) : les factories sont importees localement dans _do_initialize().
"""

import logging
import os
import threading

from config.constants import PROJECT_DIR, REFRESH_INTERVAL, WARMUP_DELAY

_logger = logging.getLogger("jarvis.context")


class AppContext:
    """Conteneur de tous les services metier.

    Initialisation en deux temps :
      - __init__    : leger, tous les attributs a None
      - initialize() : cree les services avec try/except par service
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
        self.status_cache: dict = {"ts": 0, "data": {}}
        self.profiles_path: str = os.path.join(PROJECT_DIR, "config", "agent_profiles.json")
        self.init_report: dict[str, str] = {}
        self._initialized = False
        # Thread coordination
        self.stop_event = threading.Event()
        self.refresh_interval = REFRESH_INTERVAL
        self.warmup_delay = WARMUP_DELAY

    def _init_service(self, name, factory):
        try:
            setattr(self, name, factory() if callable(factory) else factory)
            self.init_report[name] = "OK"
        except Exception as e:
            self.init_report[name] = f"FAIL: {e}"

    def initialize(self):
        if self._initialized:
            return
        self._initialized = True
        try:
            self._do_initialize()
        except Exception as e:  # jamais laisser initialize() planter le demarrage uvicorn
            _logger.exception("initialize() a leve — demarrage en mode degrade: %s", e)
            self.init_report.setdefault("fatal", f"FAIL: {e}")

    def _do_initialize(self):
        from agents.factory import create_agents
        from services.analytics import AnalyticsService
        from services.conversation import ConversationService
        from services.diagnostic_ext import DiagnosticExtService
        from services.file_system import FileSystemService
        from services.inference import InferenceService
        from services.log import LogService
        from services.memory import MemoryService
        from services.metrics import MetricsService
        from services.orchestrator import OrchestratorService
        from services.router import AgentRouter
        from services.toolbox import Toolbox
        from services.vector import VectorService

        self.init_report = {}
        basic = [
            ("inference", InferenceService),
            ("memory", MemoryService),
            ("vector", VectorService),
            ("log", LogService),
            ("analytics", AnalyticsService),
            ("conversations", ConversationService),
            ("metrics", MetricsService),
            ("router_svc", AgentRouter),
        ]
        for name, cls in basic:
            self._init_service(name, cls)

        if self.vector and self.conversations:
            from services.ingest_queue import IngestQueue
            self.ingest_queue = IngestQueue(self.vector)
            self.conversations.set_on_message(self.ingest_queue.enqueue)

        if self.inference and self.memory:
            self._init_service("agents", lambda: create_agents(self.inference, self.memory))

        # Conversations est fondamentalement file I/O — toujours necessaire independamment de l'IA
        # Removed condition that prevented it from initializing when inference was None

        if self.agents:
            toolbox = Toolbox(
                diagnostic_service=DiagnosticExtService(),
                file_service=FileSystemService(),
            )
            for agent in self.agents.values():
                agent.inject_toolbox(toolbox)
            self._init_service("toolbox", lambda: toolbox)

        needed = [self.inference, self.memory, self.vector, self.log,
                  self.analytics, self.conversations, self.metrics,
                  self.agents, self.router_svc, self.toolbox]
        if all(needed):
            self._init_service("orchestrator", lambda: OrchestratorService(
                inference=self.inference, memory=self.memory, vector=self.vector,
                log=self.log, analytics=self.analytics, conversations=self.conversations,
                metrics=self.metrics, agents=self.agents, router_service=self.router_svc,
                toolbox=self.toolbox,
            ))

    @property
    def ready(self) -> bool:
        return self.orchestrator is not None
