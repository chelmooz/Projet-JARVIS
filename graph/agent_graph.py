"""AgentGraph — Moteur d'exécution séquentiel pour les tâches JARVIS.

Responsabilité unique : Orchestrer le flux de traitement d'une tâche (5 étapes).
Ne gère PAS :
- L'instanciation des services (DIP strict).
- La gestion des pipelines (déléguée à PipelineService).
- Le masquage des erreurs (Fail Fast : les exceptions remontent à l'Orchestrateur).
"""
import logging
from typing import Any, Callable

from services.pipeline_steps import (
    format_output,
    query_model,
    retrieve_context,
    save_results,
    select_agent,
    select_model,
)

_logger = logging.getLogger("jarvis.graph")


class AgentGraph:
    """Orchestrateur séquentiel pour une tâche JARVIS.
    
    Toutes les dépendances doivent être injectées via le constructeur (DIP).
    """

    def __init__(
        self,
        model_provider: Any,
        memory: Any,
        vector_store: Any,
        toolbox: Any,
        agents: dict,
        router: Any,
        pipeline: Any,
        conversations: Any,
        agent_supervisor: Any,
    ):
        # Fail Fast : aucune dépendance ne doit être None
        required = {
            "model_provider": model_provider, "memory": memory, 
            "vector_store": vector_store, "toolbox": toolbox,
            "agents": agents, "router": router, 
            "pipeline": pipeline, "conversations": conversations,
            "agent_supervisor": agent_supervisor
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(f"Dépendances manquantes dans AgentGraph (DIP) : {missing}")

        self.router = router
        self.model_provider = model_provider
        self.memory = memory
        self.vector_store = vector_store
        self.conversations = conversations
        self.agents = agents
        self.toolbox = toolbox
        self.pipeline = pipeline
        self.agent_supervisor = agent_supervisor

    def _run_agent_step(self, agent_key: str, prompt: str, model: str | None = None) -> str:
        """Exécute une étape de pipeline via un agent. Retourne la réponse textuelle."""
        agent = self.agents.get(agent_key)
        if not agent:
            # Fail Fast : on lève une exception au lieu de retourner une string d'erreur
            raise ValueError(f"Agent '{agent_key}' introuvable dans le registre")
            
        if not model:
            model = select_model(agent_key, None, self.model_provider)
            
        result = self.agent_supervisor.run(
            agent, prompt, model, {},
            cancel_fn=lambda: self.model_provider.cancel_current(),
        )
        return result.get("response", "")

    def run(self, task: str, image: str | None = None, conversation_id: str | None = None) -> dict:
        """Exécute une tâche JARVIS complète (5 étapes séquentielles).
        
        Les exceptions ne sont pas capturées ici. Elles remontent à OrchestratorService
        qui gérera le fallback métier de manière explicite.
        """
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
        
        # Pipeline séquentiel explicite (KISS)
        state = select_agent(state, self.router)
        state = retrieve_context(state, self.memory, self.vector_store, self.model_provider)
        state = query_model(
            state, self.model_provider, self.agents, self.toolbox,
            lambda ak, img, inf: select_model(ak, img, inf),
        )
        state = save_results(state, self.memory, self.vector_store)
        
        return format_output(state)
