"""OrchestratorService — Coordination métier des requêtes JARVIS.

Point d'entrée unique pour le traitement des tâches :
  1. Routage vers le bon agent (via AgentGraph ou fallback vision)
  2. Tracking analytics
  3. Sauvegarde en conversation
  4. Compteurs de métriques
"""
import time
import traceback
import uuid

from graph import AgentGraph
from services.selector import select_vision_model


class OrchestratorService:
    """Coordination métier des requêtes JARVIS.

    Point d'entrée unique pour le traitement des tâches :
      1. Routage vers le bon agent (via AgentGraph ou fallback vision)
      2. Tracking analytics
      3. Sauvegarde en conversation
      4. Compteurs de métriques
    """

    def __init__(self, inference, memory, vector, log, analytics,
                 conversations, metrics, agents, router_service, toolbox=None,
                 agent_graph_factory=None, vision_model_selector=None):
        self.inference = inference
        self.memory = memory
        self.vector = vector
        self.log = log
        self.analytics = analytics
        self.conversations = conversations
        self.metrics = metrics
        self.agents = agents
        self.router_service = router_service
        self.toolbox = toolbox
        self.agent_graph_factory = agent_graph_factory or (lambda: AgentGraph(
            model_provider=inference, memory=memory, vector_store=vector,
            toolbox=toolbox, agents=agents, router=router_service,
            conversations=conversations,
        ))
        self.vision_model_selector = vision_model_selector or select_vision_model

    def handle_request(self, task: str, image: str | None, conv_id: str | None) -> dict:
        """Point d'entrée unique : traite une tâche JARVIS complète."""
        if not conv_id:
            conv_id = str(uuid.uuid4())[:8]
        self.metrics.incr_requests("/api/jarvis")
        start = time.time()

        if image:
            result = self._handle_vision(task, image, conv_id, start)
        else:
            try:
                g = self.agent_graph_factory()
                result = g.run(task, conversation_id=conv_id)
            except Exception as e:
                detail = traceback.format_exc()
                max_len = 4000 if getattr(self.log, "dev_mode", False) else 500
                self.log.log("ERROR", f"Graph failed: {e}\n{detail[:max_len]}")
                agent_key = self.router_service.select_agent(task)
                result = self._simulation_response(task, agent_key, str(e), start)
            else:
                result = self._handle_success(result, task, conv_id, start)

        if isinstance(result, dict):
            result["conversation_id"] = conv_id
        return result

    def _handle_vision(self, task, image, conv_id, start):
        agent_key = "vision"
        context = {"image": image, "recent_tasks": self.memory.get_habits(), "similar_cases": []}
        model_name = self.vision_model_selector(self.inference)
        if not model_name:
            err = {"error": "Aucun modele vision disponible", "agent": agent_key}
            return err
        result = self._run_vision(task, model_name, context, agent_key, conv_id, start)
        return result

    def _handle_success(self, result, task, conv_id, start):
        agent_key = result.get("agent", self.router_service.select_agent(task))
        model_name = result.get("model", "auto")
        self.log.log("INFO", f"graph agent={agent_key} model={model_name}")
        latency_ms = (time.time() - start) * 1000
        self.analytics.track_query(agent_key, model_name, latency_ms=latency_ms, success=True)
        return result

    def _simulation_response(self, task, agent_key, error, start):
        """Construit une réponse de fallback quand AgentGraph échoue."""
        latency_ms = (time.time() - start) * 1000
        self.analytics.track_query(agent_key, "auto", latency_ms=latency_ms, success=False)
        return {
            "response": f"[Mode simulation] Agent {agent_key} : {error}",
            "agent": agent_key, "agent_key": agent_key,
            "model": "auto", "backend": "ollama", "suggested_skill": None,
        }

    def _run_vision(self, task, model_name, context, agent_key, conv_id, start):
        """Exécute une tâche vision avec l'agent dédié."""
        try:
            result = self.agents["vision"].run(task, model_name, context)
        except Exception as e:
            self.log.log("ERROR", f"Vision failed: {e}")
            latency_ms = (time.time() - start) * 1000
            self.analytics.track_query(agent_key, model_name, latency_ms=latency_ms, success=False)
            return {"error": str(e), "agent": agent_key}
        self.memory.update_habits({"task": task, "agent": agent_key})
        self.conversations.add_message(conv_id, "user", task)
        self.conversations.add_message(conv_id, "assistant",
            result.get("response", ""), agent=agent_key, model=model_name)
        self.log.log("INFO", f"agent=vision model={model_name}")
        latency_ms = (time.time() - start) * 1000
        self.analytics.track_query(agent_key, model_name, latency_ms=latency_ms, success=True)
        return result
