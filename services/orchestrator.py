"""OrchestratorService — Coordination métier des requêtes JARVIS.

Point d'entrée unique pour le traitement des tâches :
  1. Routage vers le bon agent (via AgentGraph ou fallback vision)
  2. Tracking analytics
  3. Sauvegarde en conversation
  4. Compteurs de métriques
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Protocol

from ports import (
    AnalyticsPort,
    ChatPort,
    ConversationPort,
    HabitPort,
    LogPort,
    MetricsPort,
    ModelRegistryPort,
    MultimodalPort,
    VectorPort,
)
from services.selector import select_vision_model

_logger = logging.getLogger("jarvis.orchestrator")


# ---------------------------------------------------------------------------
# Contrats structurels (ISP) pour les dépendances injectées
# ---------------------------------------------------------------------------
class _InferenceLike(ChatPort, MultimodalPort, ModelRegistryPort, Protocol):
    """Fournisseur d'inférence complet (texte + vision + registry)."""


class _AgentLike(Protocol):
    """Tout agent exposant ``run(task, model, context)``."""
    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]: ...


class _RouterLike(Protocol):
    """Routeur exposant ``select_agent(task)``."""
    def select_agent(self, task: str) -> str: ...


class AgentGraphPort(Protocol):
    """Interface attendue pour le graphe d'agents (DIP)."""
    def run(
        self,
        task: str,
        image: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]: ...


class OrchestratorService:
    """Coordination métier des requêtes JARVIS.
    
    Responsabilités :
    - Orchestrer le flux de traitement d'une requête.
    - Déléguer l'exécution au graphe d'agents ou aux agents vision.
    - Assurer la télémétrie (analytics, metrics, logs).
    
    Ne gère PAS :
    - L'implémentation concrète des agents.
    - La persistance (déléguée aux services injectés).
    """

    def __init__(
        self,
        inference: _InferenceLike,
        memory: HabitPort,
        vector: VectorPort,
        log: LogPort,
        analytics: AnalyticsPort,
        conversations: ConversationPort,
        metrics: MetricsPort,
        agents: dict[str, _AgentLike],
        router_service: _RouterLike,
        toolbox: Any | None = None,
        agent_graph_factory: Callable[[], AgentGraphPort] | None = None,
        vision_model_selector: Callable[[_InferenceLike], str | None] | None = None,
    ) -> None:
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
        
        # DIP: Plus d'import concret de AgentGraph ici.
        # La factory doit être injectée par le Composition Root.
        if agent_graph_factory is None:
            raise ValueError("agent_graph_factory doit être injecté (DIP).")
        self.agent_graph_factory = agent_graph_factory
        
        self.vision_model_selector = vision_model_selector or select_vision_model

    def handle_request(
        self, task: str, image: str | None, conv_id: str | None
    ) -> dict[str, Any]:
        """Point d'entrée unique : traite une tâche JARVIS complète."""
        if not conv_id:
            conv_id = str(uuid.uuid4())[:8]
            
        self.metrics.incr_requests("/api/jarvis")
        start = time.time()

        if image:
            result = self._handle_vision(task, image, conv_id, start)
        else:
            result = self._handle_text(task, conv_id, start)

        if isinstance(result, dict):
            result["conversation_id"] = conv_id
        return result

    def _handle_text(self, task: str, conv_id: str, start: float) -> dict[str, Any]:
        """Gère les requêtes textuelles via le graphe d'agents."""
        try:
            graph = self.agent_graph_factory()
            result = graph.run(task, image=None, conversation_id=conv_id)
        except Exception as e:
            # Observabilité : On log l'erreur complète via le logger standard.
            _logger.exception("Échec critique du graphe d'agents pour la tâche: %s", task)
            self.log.log("ERROR", f"Graph failed: {e}")
            
            # Fallback métier explicite
            agent_key = self.router_service.select_agent(task)
            return self._build_fallback_response(task, agent_key, str(e), start)
        
        return self._finalize_success(result, task, start)

    def _handle_vision(
        self, task: str, image: str, conv_id: str, start: float
    ) -> dict[str, Any]:
        """Gère les requêtes vision."""
        agent_key = "vision"
        model_name = self.vision_model_selector(self.inference)
        
        if not model_name:
            self.log.log("ERROR", "Aucun modèle vision disponible")
            return {"error": "Aucun modele vision disponible", "agent": agent_key}

        context: dict[str, Any] = {
            "image": image,
            "recent_tasks": self.memory.get_habits(),
            "similar_cases": self.vector.search(task, top_k=3) if self.vector else [],
        }

        try:
            result = self.agents[agent_key].run(task, model_name, context)
        except Exception as e:
            _logger.exception("Échec de l'agent vision")
            self.log.log("ERROR", f"Vision failed: {e}")
            self._track_metrics(agent_key, model_name, start, success=False)
            return {"error": str(e), "agent": agent_key}

        # Sauvegarde et télémétrie
        self.memory.update_habits({"task": task, "agent": agent_key})
        self.conversations.add_message(conv_id, "user", task)
        self.conversations.add_message(
            conv_id, "assistant", result.get("response", ""), 
            agent=agent_key, model=model_name
        )
        
        self._track_metrics(agent_key, model_name, start, success=True)
        self.log.log("INFO", f"agent=vision model={model_name}")
        return result

    def _finalize_success(
        self, result: dict[str, Any], task: str, start: float
    ) -> dict[str, Any]:
        """Finalise une requête réussie : télémétrie et formatage."""
        agent_key = result.get("agent") or self.router_service.select_agent(task)
        model_name = result.get("model") or "auto"
        
        self._track_metrics(agent_key, model_name, start, success=True)
        self.log.log("INFO", f"graph agent={agent_key} model={model_name}")
        return result

    def _track_metrics(
        self, agent_key: str, model_name: str, start: float, success: bool
    ) -> None:
        """Centralise le tracking analytics et métriques."""
        latency_ms = (time.time() - start) * 1000
        self.analytics.track_query(
            agent=agent_key,
            model=model_name,
            latency_ms=latency_ms,
            success=success,
        )

    def _build_fallback_response(
        self, task: str, agent_key: str, error: str, start: float
    ) -> dict[str, Any]:
        """Construit une réponse de fallback explicite."""
        self._track_metrics(agent_key, "auto", start, success=False)
        return {
            "response": f"[Mode simulation] Agent {agent_key} : {error}",
            "agent": agent_key,
            "agent_key": agent_key,
            "model": "auto",
            "backend": "ollama",
            "suggested_skill": None,
        }


__all__ = ["OrchestratorService"]
