"""Tests TDD pour services/orchestrator.py — cœur métier orchestration."""

from __future__ import annotations

import pytest

from services.orchestrator import OrchestratorService


class FakeInference:
    """Fake inference implementing required ports."""

    def query(self, prompt: str, model: str | None = None, system: str | None = None) -> str:
        return f"response for {prompt[:20]}"

    def chat(self, model: str, messages: list[dict]) -> dict:
        return {"response": "chat response", "agent": "test", "model": model, "backend": "ollama"}

    def query_multimodal(self, model: str, prompt: str, image_base64: str) -> dict:
        return {"response": "vision response"}

    def embed(self, text: str, model: str | None = None) -> list[float]:
        return [0.1] * 384

    def list_models(self) -> list[str]:
        return ["qwen2.5:7b", "nomic-embed-text"]

    def is_available(self, model: str) -> bool:
        return True

    def first_available(self) -> str | None:
        return "qwen2.5:7b"

    def get_active_backend(self) -> str:
        return "ollama"

    def ping(self) -> bool:
        return True

    def cancel_current(self, thread_id: int) -> None:
        pass


class FakeMemory:
    """Fake habit memory."""

    def __init__(self):
        self.habits = []

    def get_habits(self, limit: int = 10) -> list[dict]:
        return self.habits[:limit]

    def update_habits(self, entry: dict) -> None:
        self.habits.append(entry)

    def is_healthy(self) -> bool:
        return True


class FakeVector:
    """Fake vector search."""

    def __init__(self):
        self.indexed = []

    def index(self, text: str, metadata: dict | None = None) -> None:
        self.indexed.append({"text": text, "metadata": metadata or {}})

    def index_batch(self, documents: list[tuple[str, dict | None]]) -> None:
        for text, meta in documents:
            self.index(text, meta)

    def vectorize_pending(self) -> int:
        return 0

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        return [{"id": "1", "text": f"similar to {query}", "score": 0.9}]

    def stats(self) -> dict:
        return {"count": len(self.indexed)}

    def preload(self) -> None:
        pass

    def is_healthy(self) -> bool:
        return True


class FakeLog:
    """Fake logger."""

    def __init__(self):
        self.logs = []

    def log(self, level: str, message: str) -> None:
        self.logs.append({"level": level, "message": message})


class FakeAnalytics:
    """Fake analytics."""

    def __init__(self):
        self.queries = []

    def track_query(
        self,
        agent: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
        source: str = "chat",
    ) -> None:
        self.queries.append({"agent": agent, "model": model, "latency_ms": latency_ms, "success": success})

    def get_stats(self) -> dict:
        return {"total": len(self.queries)}

    def get_most_used(self) -> dict:
        return {}


class FakeConversations:
    """Fake conversations."""

    def __init__(self):
        self.convs = {}

    def create(self, title: str = "Nouvelle conversation") -> str:
        return "conv-123"

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        agent: str | None = None,
        model: str | None = None,
        backend: str | None = None,
    ) -> None:
        pass

    def get_conversation(self, conv_id: str) -> dict | None:
        return None

    def list_all(self) -> list[dict]:
        return []

    def delete(self, conv_id: str) -> None:
        pass

    def delete_all(self) -> None:
        pass

    def is_healthy(self) -> bool:
        return True


class FakeMetrics:
    """Fake metrics."""

    def __init__(self):
        self.counters = {}

    def incr_requests(self, endpoint: str = "/api/jarvis") -> None:
        self.counters[endpoint] = self.counters.get(endpoint, 0) + 1

    def incr_pipeline_run(self) -> None:
        pass

    def incr_errors(self) -> None:
        pass

    def get_metrics(self) -> dict:
        return self.counters


class FakeRouter:
    """Fake router."""

    def select_agent(self, task: str) -> str:
        if task.startswith("@cyber"):
            return "cyber"
        if "network" in task.lower():
            return "network"
        return "dev"


class FakeAgent:
    """Fake agent with run method."""

    def __init__(self, name: str):
        self.name = name
        self.calls = []

    def run(self, task: str, model: str, context: dict) -> dict:
        self.calls.append({"task": task, "model": model, "context": context})
        return {
            "response": f"Agent {self.name} response",
            "agent": self.name,
            "model": model,
            "backend": "ollama",
            "suggested_skill": None,
        }


class FakeAgentGraph:
    """Fake agent graph."""

    def __init__(self, should_fail: bool = False, fail_message: str = "graph error"):
        self.should_fail = should_fail
        self.fail_message = fail_message
        self.calls = []

    async def run(self, task: str, image: str | None = None, conversation_id: str | None = None) -> dict:
        self.calls.append({"task": task, "image": image, "conversation_id": conversation_id})
        if self.should_fail:
            raise RuntimeError(self.fail_message)
        return {
            "response": "Graph response",
            "agent": "dev",
            "model": "qwen2.5:7b",
            "backend": "ollama",
            "suggested_skill": None,
        }


def build_service(
    graph_should_fail: bool = False,
    graph_fail_message: str = "graph error",
    inference: FakeInference | None = None,
    vision_model_selector=None,
) -> OrchestratorService:
    """Build OrchestratorService with fakes."""
    inference = inference or FakeInference()

    def _graph_factory():
        return FakeAgentGraph(should_fail=graph_should_fail, fail_message=graph_fail_message)

    agents = {
        "dev": FakeAgent("dev"),
        "cyber": FakeAgent("cyber"),
        "network": FakeAgent("network"),
        "vision": FakeAgent("vision"),
    }

    def _default_vision_selector(inf):
        return "llama3.2-vision"

    return OrchestratorService(
        inference=inference,
        memory=FakeMemory(),
        vector=FakeVector(),
        log=FakeLog(),
        analytics=FakeAnalytics(),
        conversations=FakeConversations(),
        metrics=FakeMetrics(),
        agents=agents,
        router_service=FakeRouter(),
        toolbox=None,
        agent_graph_factory=_graph_factory,
        vision_model_selector=vision_model_selector or _default_vision_selector,
    )


class TestOrchestratorRouting:
    """Tests de routage nominal et fallback."""

    @pytest.mark.asyncio
    async def test_handle_text_nominal_routes_to_graph(self):
        """Texte nominal : délègue au graphe d'agents, retourne réponse formatée."""
        service = build_service()
        result = await service.handle_request("hello world", image=None, conv_id="conv-1")

        assert result["response"] == "Graph response"
        assert result["agent"] == "dev"
        assert result["conversation_id"] == "conv-1"
        # Le graphe a été appelé (nouvelle instance à chaque fois, résultat prouve que ça a marché)

    @pytest.mark.asyncio
    async def test_handle_text_agent_absent_fallback_router(self):
        """Graphe échoue (agent absent) : fallback vers router explicite."""
        service = build_service(graph_should_fail=True, graph_fail_message="Agent not found")
        result = await service.handle_request("test task", image=None, conv_id="conv-2")

        assert result["agent"] == "dev"  # fallback router
        assert "Mode simulation" in result["response"]
        # La réponse de fallback n'a pas de clé "error", elle a "response" avec le message
        assert "error" not in result or result.get("error") is None

    @pytest.mark.asyncio
    async def test_handle_text_agent_error_fallback_response(self):
        """Graphe lève exception : réponse de fallback structurée sans crash."""
        service = build_service(graph_should_fail=True, graph_fail_message="Internal error")
        result = await service.handle_request("test task", image=None, conv_id="conv-3")

        assert result["agent"] == "dev"
        assert result["model"] == "auto"
        assert result["backend"] == "ollama"
        assert "Internal error" in result["response"]

    @pytest.mark.asyncio
    async def test_handle_vision_nominal(self):
        """Vision nominal : utilise modèle vision, retourne réponse."""
        service = build_service()
        result = await service.handle_request("analyse image", image="base64data", conv_id="conv-4")

        assert result["agent"] == "vision"
        assert "response" in result
        assert result["conversation_id"] == "conv-4"

    @pytest.mark.asyncio
    async def test_handle_vision_no_model_available(self):
        """Vision sans modèle dispo : erreur explicite."""

        def no_vision_model(inf):
            return None

        service = build_service(vision_model_selector=no_vision_model)
        result = await service.handle_request("analyse", image="base64", conv_id="conv-5")

        assert result["error"] == "Aucun modele vision disponible"
        assert result["agent"] == "vision"

    @pytest.mark.asyncio
    async def test_handle_vision_agent_error(self):
        """Vision agent lève exception : fallback response."""

        # On crée un agent vision qui échoue
        class FailingAgent:
            def run(self, task, model, context):
                raise RuntimeError("Vision agent crashed")

        agents = {
            "dev": FakeAgent("dev"),
            "vision": FailingAgent(),
        }

        service = OrchestratorService(
            inference=FakeInference(),
            memory=FakeMemory(),
            vector=FakeVector(),
            log=FakeLog(),
            analytics=FakeAnalytics(),
            conversations=FakeConversations(),
            metrics=FakeMetrics(),
            agents=agents,
            router_service=FakeRouter(),
            toolbox=None,
            agent_graph_factory=lambda: FakeAgentGraph(),
            vision_model_selector=lambda inf: "llama3.2-vision",
        )

        result = await service.handle_request("analyse", image="base64", conv_id="conv-6")
        assert result["error"] == "Vision agent crashed"
        assert result["agent"] == "vision"

    @pytest.mark.asyncio
    async def test_conversation_id_generated_when_missing(self):
        """Si conv_id absent : en génère un."""
        service = build_service()
        result = await service.handle_request("test", image=None, conv_id=None)

        assert result["conversation_id"] is not None
        assert len(result["conversation_id"]) > 0

    @pytest.mark.asyncio
    async def test_metrics_incremented(self):
        """Métriques incrémentées à chaque requête."""
        service = build_service()
        await service.handle_request("test", image=None, conv_id="conv-7")

        assert service.metrics.counters.get("/api/jarvis", 0) == 1

    @pytest.mark.asyncio
    async def test_analytics_tracked_on_success(self):
        """Analytics trackées sur succès."""
        service = build_service()
        await service.handle_request("test", image=None, conv_id="conv-8")

        assert len(service.analytics.queries) == 1
        assert service.analytics.queries[0]["success"] is True
        assert service.analytics.queries[0]["agent"] == "dev"

    @pytest.mark.asyncio
    async def test_analytics_tracked_on_failure(self):
        """Analytics trackées sur échec (fallback)."""
        service = build_service(graph_should_fail=True)
        await service.handle_request("test", image=None, conv_id="conv-9")

        assert len(service.analytics.queries) == 1
        assert service.analytics.queries[0]["success"] is False

    @pytest.mark.asyncio
    async def test_log_error_on_graph_failure(self):
        """Erreur graph logguée."""
        service = build_service(graph_should_fail=True, graph_fail_message="Graph crashed")
        await service.handle_request("test", image=None, conv_id="conv-10")

        error_logs = [entry for entry in service.log.logs if entry["level"] == "ERROR"]
        assert any("Graph failed" in entry["message"] for entry in error_logs)

    @pytest.mark.asyncio
    async def test_log_info_on_success(self):
        """Info logguée sur succès."""
        service = build_service()
        await service.handle_request("test", image=None, conv_id="conv-11")

        info_logs = [entry for entry in service.log.logs if entry["level"] == "INFO"]
        assert any("graph agent=" in entry["message"] for entry in info_logs)

    @pytest.mark.asyncio
    async def test_habits_updated_on_vision_success(self):
        """Habitudes mises à jour sur succès vision."""
        service = build_service()
        await service.handle_request("analyse", image="base64", conv_id="conv-12")

        assert len(service.memory.habits) == 1
        assert service.memory.habits[0]["agent"] == "vision"


class TestOrchestratorInjection:
    """Tests d'injection de dépendances (DIP)."""

    def test_requires_agent_graph_factory(self):
        """agent_graph_factory obligatoire (DIP)."""
        with pytest.raises(ValueError, match="agent_graph_factory doit être injecté"):
            OrchestratorService(
                inference=FakeInference(),
                memory=FakeMemory(),
                vector=FakeVector(),
                log=FakeLog(),
                analytics=FakeAnalytics(),
                conversations=FakeConversations(),
                metrics=FakeMetrics(),
                agents={},
                router_service=FakeRouter(),
                toolbox=None,
                agent_graph_factory=None,  # Doit lever
            )

    def test_vision_model_selector_default(self):
        """Sélecteur vision par défaut injecté si absent."""
        from services.selector import select_vision_model

        # Build service without passing vision_model_selector to test default
        inference = FakeInference()

        def _graph_factory():
            return FakeAgentGraph()

        agents = {"dev": FakeAgent("dev"), "vision": FakeAgent("vision")}

        service = OrchestratorService(
            inference=inference,
            memory=FakeMemory(),
            vector=FakeVector(),
            log=FakeLog(),
            analytics=FakeAnalytics(),
            conversations=FakeConversations(),
            metrics=FakeMetrics(),
            agents=agents,
            router_service=FakeRouter(),
            toolbox=None,
            agent_graph_factory=_graph_factory,
            vision_model_selector=None,  # None pour tester le défaut
        )
        assert service.vision_model_selector is select_vision_model

    def test_vision_model_selector_custom(self):
        """Sélecteur vision custom respecté."""

        def custom(inf):
            return "custom-model"

        service = build_service(vision_model_selector=custom)
        assert service.vision_model_selector is custom


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
