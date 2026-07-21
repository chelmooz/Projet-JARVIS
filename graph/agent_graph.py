"""AgentGraph — Moteur d'exécution séquentiel pour les tâches JARVIS.

Responsabilité unique : Orchestrer le flux de traitement d'une tâche (5 étapes).
Ne gère PAS :
- L'instanciation des services (DIP strict).
- La gestion des pipelines (déléguée à PipelineService).
- Le masquage des erreurs (Fail Fast : les exceptions remontent à l'Orchestrateur).
"""
from __future__ import annotations

import logging
from typing import Any

from ports import ConversationPort, HabitPort, ModelRegistryPort, VectorPort
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
    Les ports typés garantissent le contrat structurel. Les dépendances sans
    port dédié sont typées `object` (pas `Any`) pour forcer le cast explicite.
    """

    def __init__(
        self,
        model_provider: ModelRegistryPort,
        memory: HabitPort,
        vector_store: VectorPort,
        toolbox: object,
        agents: dict[str, object],
        router: object,
        pipeline: object,
        conversations: ConversationPort,
        agent_supervisor: object,
    ) -> None:
        required = {
            "model_provider": model_provider,
            "memory": memory,
            "vector_store": vector_store,
            "toolbox": toolbox,
            "agents": agents,
            "router": router,
            "pipeline": pipeline,
            "conversations": conversations,
            "agent_supervisor": agent_supervisor,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(f"Dépendances manquantes dans AgentGraph (DIP) : {missing}")

        self.model_provider = model_provider
        self.memory = memory
        self.vector_store = vector_store
        self.toolbox = toolbox
        self.agents = agents
        self.router = router
        self.pipeline = pipeline  # Injecté pour compat. Non utilisé dans run().
        self.conversations = conversations  # Injecté pour compat. Non utilisé dans run().
        self.agent_supervisor = agent_supervisor

    def _run_agent_step(self, agent_key: str, prompt: str, model: str | None = None) -> str:
        """Exécute une étape de pipeline via un agent. Retourne la réponse textuelle.

        NOTE: Méthode conservée pour compat avec d'éventuels appels externes
        (tests, pipelines custom). Non utilisée dans run() standard.
        """
        agent = self.agents.get(agent_key)
        if not agent:
            raise ValueError(f"Agent '{agent_key}' introuvable dans le registre")

        if not model:
            model = select_model(agent_key, None, self.model_provider)

        result = self.agent_supervisor.run(
            agent, prompt, model, {},
            cancel_fn=lambda: self.model_provider.cancel_current(),
        )
        return result.get("response", "")

    def run(self, task: str, image: str | None = None, conversation_id: str | None = None) -> dict[str, Any]:
        """Exécute une tâche JARVIS complète (5 étapes séquentielles).

        Les exceptions ne sont pas capturées ici. Elles remontent à OrchestratorService
        qui gérera le fallback métier de manière explicite.

        NOTE: `state` est un dict mutable partagé entre les steps. Cible :
        dataclass `PipelineState` dans models/ pour typer le contrat d'état.
        """
        state: dict[str, Any] = {
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

        state = select_agent(state, self.router)
        state = retrieve_context(state, self.memory, self.vector_store, self.model_provider)
        state = query_model(
            state, self.model_provider, self.agents, self.toolbox, select_model,
        )
        state = save_results(state, self.memory, self.vector_store)

        return format_output(state)


def create_agent_graph(
    model_provider: Any,
    memory: Any,
    vector_store: Any,
    toolbox: Any,
    agents: dict[str, object],
    router: Any,
    pipeline: Any,
    conversations: Any,
    agent_supervisor: Any,
) -> AgentGraph:
    """Factory pour créer un AgentGraph avec toutes ses dépendances (DIP)."""
    return AgentGraph(
        model_provider=model_provider,
        memory=memory,
        vector_store=vector_store,
        toolbox=toolbox,
        agents=agents,
        router=router,
        pipeline=pipeline,
        conversations=conversations,
        agent_supervisor=agent_supervisor,
    )


__all__ = ["AgentGraph", "create_agent_graph"]
