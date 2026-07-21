# Dans _do_initialize() de controllers/di.py

# ... (après l'instanciation de self.toolbox)

# 4.5 Injection de la toolbox dans les agents (déplacée depuis AgentGraph)
for agent in self.agents.values():
    agent.inject_toolbox(self.toolbox)

# 4.6 Instanciation de AgentSupervisor (à importer en haut de di.py)
from agents.supervisor import AgentSupervisor
agent_supervisor = AgentSupervisor()

# 5. Orchestrateur (Composition Root finale)
self.orchestrator = OrchestratorService(
    # ... (autres dépendances inchangées)
    
    # DIP: Injection de la factory concrète pour AgentGraph
    agent_graph_factory=lambda: AgentGraph(
        model_provider=self.inference,
        memory=self.memory,
        vector_store=self.vector,
        toolbox=self.toolbox,
        agents=self.agents,
        router=self.router_svc,
        conversations=self.conversations,
        pipeline=self.pipeline, # À ajouter si pas déjà fait
        agent_supervisor=agent_supervisor, # Nouvelle dépendance injectée
    )
)
