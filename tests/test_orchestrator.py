"""Tests pour OrchestratorService — Coordination métier.

Posture TDD stricte :
- Aucun MagicMock : utilisation exclusive des Fakes définis dans conftest.py.
- Tests centrés sur le comportement public (handle_request).
- Suppression des tests de méthodes privées (_build_fallback_response, etc.).
- Suppression des patchs globaux (injection via le constructeur).
"""
import pytest


class TestOrchestratorTextFlow:
    """Tests du flux textuel (via AgentGraph)."""

    def test_success_calls_graph_and_tracks_metrics(self, orchestrator, fake_metrics, fake_log):
        """Vérifie le succès, l'incrémentation des métriques et le log."""
        result = orchestrator.handle_request("debug code", image=None, conv_id="conv123")
        
        assert result["response"] == "Graph OK"
        assert result["conversation_id"] == "conv123"
        assert fake_metrics.requests == 1
        assert any("graph agent=dev" in msg for _, msg in fake_log.logs)

    def test_failure_returns_explicit_fallback(
        self, fake_inference, fake_memory, fake_vector, fake_log, 
        fake_analytics, fake_conversations, fake_metrics, fake_agents, 
        fake_router, fake_toolbox
    ):
        """Vérifie le fallback métier et l'observabilité en cas d'erreur critique."""
        from services.orchestrator import OrchestratorService
        
        def failing_graph_factory():
            class FailingGraph:
                def run(self, task, conversation_id):
                    raise RuntimeError("Ollama down")
            return FailingGraph()
            
        # On override le router pour forcer un agent spécifique dans le fallback
        fake_router.select_agent = lambda task: "cyber"
        
        svc = OrchestratorService(
            inference=fake_inference, memory=fake_memory, vector=fake_vector,
            log=fake_log, analytics=fake_analytics, conversations=fake_conversations,
            metrics=fake_metrics, agents=fake_agents, router_service=fake_router,
            toolbox=fake_toolbox, agent_graph_factory=failing_graph_factory,
        )
        
        result = svc.handle_request("scan network", image=None, conv_id=None)
        
        assert "Mode simulation" in result["response"]
        assert result["agent"] == "cyber"
        assert any("ERROR" in level and "Graph failed" in msg for level, msg in fake_log.logs)


class TestOrchestratorVisionFlow:
    """Tests du flux vision (via Agent dédié)."""

    def test_success_persists_conversation_and_updates_habits(
        self, fake_inference, fake_memory, fake_vector, fake_log, 
        fake_analytics, fake_conversations, fake_metrics, fake_agents, 
        fake_router, fake_toolbox
    ):
        """Vérifie la persistance, les habitudes et les métriques pour la vision."""
        from services.orchestrator import OrchestratorService
        
        # Configuration du Fake Agent Vision
        fake_agents["vision"].run = lambda task, model, context: {
            "response": "I see a cat", "agent": "vision", "model": "llava"
        }
        
        svc = OrchestratorService(
            inference=fake_inference, memory=fake_memory, vector=fake_vector,
            log=fake_log, analytics=fake_analytics, conversations=fake_conversations,
            metrics=fake_metrics, agents=fake_agents, router_service=fake_router,
            toolbox=fake_toolbox, 
            agent_graph_factory=lambda: None,  # Non utilisé pour la vision
            vision_model_selector=lambda inf: "llava"
        )
        
        result = svc.handle_request("describe this", image="base64...", conv_id="conv_vision")
        
        assert result["response"] == "I see a cat"
        assert result["conversation_id"] == "conv_vision"
        
        # Vérifie la persistance (2 messages : user + assistant)
        assert len(fake_conversations.messages) == 2
        assert fake_conversations.messages[0]["role"] == "user"
        assert fake_conversations.messages[1]["role"] == "assistant"
        
        # Vérifie la mise à jour des habitudes
        assert len(fake_memory.habits) == 1
        
        # Vérifie le tracking analytics
        assert len(fake_analytics.queries) == 1
        assert fake_analytics.queries[0]["success"] is True

    def test_no_model_available_returns_error(
        self, fake_inference, fake_memory, fake_vector, fake_log, 
        fake_analytics, fake_conversations, fake_metrics, fake_agents, 
        fake_router, fake_toolbox
    ):
        """Vérifie le court-circuit si aucun modèle vision n'est trouvé."""
        from services.orchestrator import OrchestratorService
        
        svc = OrchestratorService(
            inference=fake_inference, memory=fake_memory, vector=fake_vector,
            log=fake_log, analytics=fake_analytics, conversations=fake_conversations,
            metrics=fake_metrics, agents=fake_agents, router_service=fake_router,
            toolbox=fake_toolbox, 
            agent_graph_factory=lambda: None,
            vision_model_selector=lambda inf: None  # Aucun modèle disponible
        )
        
        result = svc.handle_request("describe", image="base64...", conv_id=None)
        
        assert "error" in result
        assert "Aucun modele vision" in result["error"]

    def test_agent_crash_returns_error_dict(
        self, fake_inference, fake_memory, fake_vector, fake_log, 
        fake_analytics, fake_conversations, fake_metrics, fake_agents, 
        fake_router, fake_toolbox
    ):
        """Vérifie la gestion d'erreur si l'agent vision crash."""
        from services.orchestrator import OrchestratorService
        
        def crashing_run(task, model, context):
            raise ValueError("Vision model crashed")
            
        fake_agents["vision"].run = crashing_run
        
        svc = OrchestratorService(
            inference=fake_inference, memory=fake_memory, vector=fake_vector,
            log=fake_log, analytics=fake_analytics, conversations=fake_conversations,
            metrics=fake_metrics, agents=fake_agents, router_service=fake_router,
            toolbox=fake_toolbox, 
            agent_graph_factory=lambda: None,
            vision_model_selector=lambda inf: "llava"
        )
        
        result = svc.handle_request("describe", image="base64...", conv_id=None)
        
        assert "error" in result
        assert "Vision model crashed" in result["error"]
