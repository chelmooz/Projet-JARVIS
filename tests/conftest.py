"""Configuration pytest — Fixtures propres, Fakes et gestion des tests live.

⚠️ POSTURE TDD :
- Aucun monkey-patch de logique interne dans les tests unitaires.
- Utilisation exclusive des Fakes définis ici pour isoler le métier (Ports & Adapters).
- Les tests live sont marqués et skippés hors-ligne.
- Le hack sys.path est supprimé : exécutez pytest depuis la racine du projet.
"""
import os
import pytest
from unittest.mock import MagicMock


def _ollama_disponible() -> bool:
    """Vérifie si un serveur Ollama répond (port JARVIS 11436 / système 11434)."""
    import httpx

    for port in (11436, 11434):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/tags", timeout=1).status_code == 200:
                return True
        except Exception:
            pass
    return False


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: test nécessitant un service live (Ollama, modèle réel, Playwright)",
    )


def pytest_collection_modifyitems(config, items):
    offline_force = os.environ.get("JARVIS_OFFLINE_TESTS") == "1"
    offline = offline_force or not _ollama_disponible()
    if not offline:
        return
    skip_live = pytest.mark.skip(
        reason="Test live ignoré hors-ligne (Ollama injoignable / JARVIS_OFFLINE_TESTS=1)"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# --- Fakes pour l'isolation des tests (Ports & Adapters) ---

class FakeInferenceService:
    def __init__(self):
        self.models = ["qwen2.5", "llama3.2-vision", "ornith-1.0-9b", "deepseek-coder-v2-lite-instruct"]
    
    def resolve_model(self, model: str) -> str | None:
        return model if model in self.models else None
    
    def list_models(self) -> list[str]:
        return self.models.copy()
    
    def first_available(self) -> str | None:
        return self.models[0] if self.models else None


class FakeMemoryService:
    def __init__(self):
        self.habits = []
    
    def get_habits(self) -> list:
        return self.habits.copy()
    
    def update_habits(self, data: dict):
        self.habits.append(data)


class FakeVectorService:
    def __init__(self):
        self.store = {}


class FakeLogService:
    def __init__(self):
        self.logs = []
    
    def log(self, level: str, message: str):
        self.logs.append((level, message))


class FakeAnalyticsService:
    def __init__(self):
        self.queries = []
    
    def track_query(self, agent: str, model: str, latency_ms: float, success: bool):
        self.queries.append({
            "agent": agent, "model": model, 
            "latency_ms": latency_ms, "success": success
        })


class FakeConversationService:
    def __init__(self):
        self.messages = []
        self._on_message = None
    
    def add_message(self, conv_id: str, role: str, content: str, **kwargs):
        msg = {"conv_id": conv_id, "role": role, "content": content, **kwargs}
        self.messages.append(msg)
        if self._on_message:
            self._on_message(msg)
    
    def set_on_message(self, callback):
        self._on_message = callback


class FakeMetricsService:
    def __init__(self):
        self.requests = 0
    
    def incr_requests(self, endpoint: str):
        self.requests += 1
    
    def get_metrics(self) -> dict:
        return {"requests": self.requests, "uptime": 0}


class FakeAgentRouter:
    def select_agent(self, task: str) -> str:
        return "dev"


class FakeToolbox:
    pass


class FakeAgent:
    def __init__(self, name: str):
        self.name = name
        self.toolbox = None
    
    def inject_toolbox(self, toolbox):
        self.toolbox = toolbox
    
    def run(self, task: str, model: str, context: dict) -> dict:
        return {
            "response": f"Fake response from {self.name}", 
            "agent": self.name, 
            "model": model
        }


# --- Fixtures Pytest ---

@pytest.fixture
def fake_inference():
    return FakeInferenceService()

@pytest.fixture
def fake_memory():
    return FakeMemoryService()

@pytest.fixture
def fake_vector():
    return FakeVectorService()

@pytest.fixture
def fake_log():
    return FakeLogService()

@pytest.fixture
def fake_analytics():
    return FakeAnalyticsService()

@pytest.fixture
def fake_conversations():
    return FakeConversationService()

@pytest.fixture
def fake_metrics():
    return FakeMetricsService()

@pytest.fixture
def fake_router():
    return FakeAgentRouter()

@pytest.fixture
def fake_agents():
    return {
        "dev": FakeAgent("dev"),
        "vision": FakeAgent("vision"),
        "cyber": FakeAgent("cyber"),
        "network": FakeAgent("network"),
        "hardware": FakeAgent("hardware"),
    }

@pytest.fixture
def fake_toolbox():
    return FakeToolbox()


@pytest.fixture
def orchestrator(fake_inference, fake_memory, fake_vector, fake_log, 
                 fake_analytics, fake_conversations, fake_metrics, 
                 fake_agents, fake_router, fake_toolbox):
    """Orchestrateur câblé avec des Fakes (aucune dépendance externe)."""
    from services.orchestrator import OrchestratorService
    from graph import AgentGraph
    
    def fake_graph_factory():
        graph = MagicMock(spec=AgentGraph)
        graph.run.return_value = {
            "response": "Graph OK", 
            "agent": "dev", 
            "model": "qwen2.5"
        }
        return graph
    
    return OrchestratorService(
        inference=fake_inference,
        memory=fake_memory,
        vector=fake_vector,
        log=fake_log,
        analytics=fake_analytics,
        conversations=fake_conversations,
        metrics=fake_metrics,
        agents=fake_agents,
        router_service=fake_router,
        toolbox=fake_toolbox,
        agent_graph_factory=fake_graph_factory,
    )


@pytest.fixture
def app_context(orchestrator, fake_inference, fake_memory, fake_vector, fake_log,
                fake_analytics, fake_conversations, fake_metrics, fake_agents, 
                fake_router, fake_toolbox):
    """Contexte applicatif complet prêt pour les tests d'intégration."""
    from controllers.di import AppContext
    
    ctx = AppContext()
    ctx.inference = fake_inference
    ctx.memory = fake_memory
    ctx.vector = fake_vector
    ctx.log = fake_log
    ctx.analytics = fake_analytics
    ctx.conversations = fake_conversations
    ctx.metrics = fake_metrics
    ctx.agents = fake_agents
    ctx.router_svc = fake_router
    ctx.toolbox = fake_toolbox
    ctx.orchestrator = orchestrator
    ctx._initialized = True
    return ctx


@pytest.fixture
def client(app_context, monkeypatch):
    """Client de test FastAPI avec contexte injecté (sans état global réel)."""
    from fastapi.testclient import TestClient
    import controllers.context as ctx_module
    
    # Patch de la façade legacy pour pointer vers notre contexte fake
    # C'est le seul endroit où monkeypatch est autorisé : le wiring de test.
    monkeypatch.setattr(ctx_module, "get_context", lambda: app_context)
    monkeypatch.setattr(ctx_module, "_ctx", app_context)
    
    app = ctx_module.build_app()
    return TestClient(app)
