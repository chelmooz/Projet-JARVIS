"""AgentGraph — Moteur d'exécution en 5 étapes séquentielles pour les tâches JARVIS.

Pipeline d'exécution :
  1. select_agent       → choisit l'agent (vision ou routage textuel)
  2. retrieve_context   → charge le contexte (habitudes, cas similaires)
  3. query_model        → exécute la requête via l'agent
  4. save_results       → persiste (habitudes, index vectoriel, conversation)
  5. format_output      → construit la réponse structurée

Chaque étape est protégée par _step() qui capture les exceptions.
"""
from agents.factory import create_agents
from agents.supervisor import AgentSupervisor
from services.conversation import ConversationService
from services.diagnostic_ext import DiagnosticExtService
from services.file_system import FileSystemService
from services.inference import InferenceService
from services.memory import MemoryService
from services.pipeline import PipelineService
from services.pipeline_steps import (
    format_output,
    query_model,
    retrieve_context,
    save_results,
    select_agent,
    select_model,
)
from services.router import AgentRouter
from services.toolbox import Toolbox
from services.vector import VectorService


class AgentGraph:
    """Orchestrateur en 5 étapes séquentielles pour une tâche JARVIS."""

    def __init__(
        self,
        model_provider=None,
        memory=None,
        vector_store=None,
        toolbox=None,
        agents=None,
        router=None,
        pipeline=None,
        conversations=None,
    ):
        self.router = router or AgentRouter()
        self.model_provider = model_provider or InferenceService()
        self.memory = memory or MemoryService()
        self.vector_store = vector_store or VectorService(inference=self.model_provider)
        self.conversations = conversations or ConversationService()
        self.agents = agents or create_agents(self.model_provider, self.memory)
        self.toolbox = toolbox or Toolbox(
            diagnostic_service=DiagnosticExtService(),
            file_service=FileSystemService(),
        )
        for agent in self.agents.values():
            agent.inject_toolbox(self.toolbox)
        self.pipeline = pipeline or PipelineService(
            agent_runner=self._run_agent_step,
            memory=self.memory,
        )

    def _run_agent_step(self, agent_key: str, prompt: str, model: str | None = None) -> str:
        """Exécute une étape de pipeline via un agent. Retourne la réponse textuelle."""
        agent = self.agents.get(agent_key)
        if not agent:
            return f"[Erreur] Agent '{agent_key}' introuvable"
        if not model:
            model = select_model(agent_key, None, self.model_provider)
        result = AgentSupervisor().run(
            agent, prompt, model, {},
            cancel_fn=lambda: self.model_provider.cancel_current(),
        )
        return result.get("response", "")

    # --- Pipeline (délégation au PipelineEngine) ---

    def run_pipeline(self, pipeline_id: str, task: str, context: dict = None) -> dict:
        """Execute pipeline."""
        return self.pipeline.run(pipeline_id, task, context)

    def list_pipelines(self) -> list[dict]:
        """List pipelines."""
        return self.pipeline.list()

    def register_pipeline(self, pipeline):
        """Register pipeline."""
        return self.pipeline.register(pipeline)

    # --- Cycle principal en 5 étapes ---

    def run(self, task: str, image: str = None, conversation_id: str = None) -> dict:
        """Exécute une tâche JARVIS complète (5 étapes séquentielles)."""
        state = {
            "task": task,
            "conversation_id": conversation_id,
            "image": image,
            "agent_key": "",
            "model": "",
            "response": "",
            "context": {},
            "result": None,
            "error": None,
            "suggested_skill": None,
        }
        state = self._step(state, lambda state: select_agent(state, self.router))
        state = self._step(state, lambda state: retrieve_context(state, self.memory, self.vector_store, self.model_provider))
        state = self._step(
            state,
            lambda state: query_model(
                state, self.model_provider, self.agents, self.toolbox,
                lambda ak, img, inf: select_model(ak, img, inf),
            ),
        )
        state = self._step(state, lambda state: save_results(state, self.memory, self.vector_store))
        return format_output(state)

    def _step(self, state: dict, fn) -> dict:
        """Exécute une étape et capture les exceptions sans planter."""
        try:
            return fn(state)
        except Exception as e:
            state["error"] = str(e)[:200]
            state["response"] = f"[Erreur] {state.get('error', '')}"
            return state



