"""AgentGraph — Moteur d'exécution séquentiel pour les tâches JARVIS.

Responsabilité unique : Orchestrer le flux de traitement d'une tâche (5 étapes).
Ne gère PAS :
- L'instanciation des services (DIP strict).
- La gestion des pipelines (déléguée à PipelineService).
- Le masquage des erreurs (Fail Fast : les exceptions remontent à l'Orchestrateur).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

from agents.supervisor import AgentLike, AgentSupervisor
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
        toolbox: object = None,
        agents: Mapping[str, AgentLike] | None = None,
        router: object = None,
        pipeline: object = None,
        conversations: ConversationPort | None = None,
        agent_supervisor: AgentSupervisor | None = None,
    ) -> None:
        required = {
            "model_provider": model_provider,
            "memory": memory,
            "vector_store": vector_store,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(f"Dépendances manquantes dans AgentGraph (DIP) : {missing}")

        self.model_provider = model_provider
        self.memory = memory
        self.vector_store = vector_store
        self.toolbox = toolbox
        self.agents = agents or {}
        self.router = router
        self.pipeline = pipeline
        self.conversations = conversations
        self.agent_supervisor = agent_supervisor

    def _run_agent_step(self, agent_key: str, prompt: str, model: str | None = None) -> str:
        """Exécute une étape de pipeline via un agent. Retourne la réponse textuelle."""
        if self.agent_supervisor is None:
            raise ValueError("AgentSupervisor non injecté — impossible d'exécuter l'agent")
        agent = self.agents.get(agent_key)
        if not agent:
            raise ValueError(f"Agent '{agent_key}' introuvable dans le registre")

        if not model:
            model = select_model(agent_key, None, self.model_provider)

        result = self.agent_supervisor.run(
            agent,
            prompt,
            model,
            {},
            cancel_fn=lambda thread_id: self.model_provider.cancel_current(thread_id),
        )
        return str(result.get("response", ""))

    async def run(self, task: str, image: str | None = None, conversation_id: str | None = None) -> dict[str, Any]:
        """Exécute une tâche JARVIS complète (5 étapes, avec parallélisation)."""
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

        # Étape 1 : sélection de l'agent (doit s'exécuter en premier)
        state = select_agent(state, self.router)

        # Étape 2 : parallélisation de retrieve_context et select_model
        # (indépendants l'un de l'autre une fois agent_key connu)
        ctx_fut = asyncio.to_thread(retrieve_context, state, self.memory, self.vector_store, self.model_provider)
        model_fut = asyncio.to_thread(select_model, state["agent_key"], None, self.model_provider)
        ctx_result, model_result = await asyncio.gather(ctx_fut, model_fut, return_exceptions=True)

        # Gestion des exceptions du pas parallèle
        if isinstance(model_result, Exception):
            state["error"] = str(model_result)
            state["response"] = f"Impossible de sélectionner un modèle : {model_result}"
            return format_output(state)

        state["context"] = ctx_result.get("context", {}) if not isinstance(ctx_result, Exception) else {}
        state["model"] = model_result

        # Étape 3 : exécution du modèle (utilise le modèle déjà sélectionné)
        state = await asyncio.to_thread(
            query_model,
            state,
            self.model_provider,
            self.agents,
            self.toolbox,
            select_model,  # sera court-circuité car state["model"] est déjà défini
        )
        # Étape 4 : sauvegarde des résultats
        state = save_results(state, self.memory, self.vector_store)

        # Étape 5 : formatage de la sortie
        return format_output(state)


def create_agent_graph(
    model_provider: Any,
    memory: Any,
    vector_store: Any,
    toolbox: Any = None,
    agents: Mapping[str, AgentLike] | None = None,
    router: Any = None,
    pipeline: Any = None,
    conversations: Any = None,
    agent_supervisor: Any = None,
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
