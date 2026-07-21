# 4.5 Injection de la toolbox dans les agents (déplacée depuis AgentGraph).
for agent in self.agents.values():
    agent.inject_toolbox(self.toolbox)

# 4.6 Garde-fou d'exécution par agent (wall-clock timeout).
from agents.supervisor import AgentSupervisor  # noqa: E402  -> à remonter en tête de module
agent_supervisor = AgentSupervisor()
self.agent_supervisor = agent_supervisor  # exposé (tests / réutilisation) ; var locale conservée

# 5. Orchestrateur (Composition Root finale).
def _build_agent_graph() -> "AgentGraph":
    """Factory nommée locale (closure sur self + agent_supervisor).

    Remplace la lambda multi-lignes : lisible, et la closure retient
    ``agent_supervisor`` même après le retour de ``_do_initialize``.
    """
    return AgentGraph(
        model_provider=self.inference,
        memory=self.memory,
        vector_store=self.vector,
        toolbox=self.toolbox,
        agents=self.agents,
        router=self.router_svc,
        pipeline=self.pipeline,
        conversations=self.conversations,
        agent_supervisor=agent_supervisor,
    )

self.orchestrator = OrchestratorService(
    # ... (autres dépendances inchangées)
    agent_graph_factory=_build_agent_graph,
)
