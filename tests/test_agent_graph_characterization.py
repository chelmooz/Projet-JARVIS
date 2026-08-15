"""Filet de caractérisation — graph/agent_graph.py (Lot 2).

Couvre : validation DIP du constructeur, `_run_agent_step` (branche
actuellement non appelée par `run()` — voir note en bas de fichier),
le flux complet de `run()` (étapes 1 à 5, parallélisation
retrieve_context/select_model, branches d'exception) et la factory
`create_agent_graph`.

Aucune assertion de comportement métier n'est inventée : chaque test
verrouille un comportement lu directement dans `graph/agent_graph.py`
et `services/pipeline_steps.py`.
"""

from __future__ import annotations

from typing import Any

import pytest

from graph.agent_graph import AgentGraph, create_agent_graph

# ---------------------------------------------------------------------------
# Doubles minimalistes, conformes aux Protocols de ports/__init__.py
# ---------------------------------------------------------------------------


class FakeModelProvider:
    def __init__(self, model: str = "qwen2.5", cancel_calls: list[int] | None = None) -> None:
        self._model = model
        self.cancel_calls: list[int] = cancel_calls if cancel_calls is not None else []

    def list_models(self) -> list[str]:
        return [self._model]

    def is_available(self, model: str) -> bool:
        return model == self._model

    def first_available(self) -> str | None:
        return self._model

    def get_active_backend(self) -> str:
        return "ollama"

    def ping(self) -> bool:
        return True

    def cancel_current(self, thread_id: int) -> None:
        self.cancel_calls.append(thread_id)

    def resolve_model(self, configured: str | None) -> str | None:
        return self._model


class FailingModelProvider(FakeModelProvider):
    """`first_available`/`resolve_model` ne trouvent rien : force l'échec de select_model."""

    def resolve_model(self, configured: str | None) -> str | None:
        return None

    def first_available(self) -> str | None:
        return None


class ValueErrorRaisingModelProvider(FakeModelProvider):
    """`resolve_model` lève directement un ValueError (pas via le RuntimeError
    de fin de `select_model`) : seul chemin qui atteint réellement le
    `except ValueError` de `_run_agent_step` (ligne 82)."""

    def resolve_model(self, configured: str | None) -> str | None:
        raise ValueError("configuration modèle invalide")


class FakeHabitMemory:
    def __init__(self, habits: list[dict[str, Any]] | None = None) -> None:
        self._habits = habits if habits is not None else []

    def get_habits(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._habits[:limit]

    def update_habits(self, entry: dict[str, Any]) -> None:
        return None

    def is_healthy(self) -> bool:
        return True


class FakeVectorStore:
    def __init__(self, search_results: list[dict[str, Any]] | None = None) -> None:
        self._search_results = search_results if search_results is not None else []
        self.indexed: list[tuple[str, dict[str, Any] | None]] = []

    def index(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        self.indexed.append((text, metadata))

    def index_batch(self, documents: list[tuple[str, dict[str, Any] | None]]) -> None:
        self.indexed.extend(documents)

    def vectorize_pending(self) -> int:
        return 0

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        return self._search_results[:top_k]

    def stats(self) -> dict[str, Any]:
        return {"count": len(self.indexed)}

    def preload(self) -> None:
        return None

    def is_healthy(self) -> bool:
        return True


class FakeRouter:
    def __init__(self, agent_key: str = "dev") -> None:
        self._agent_key = agent_key
        self.last_task: str | None = None

    def select_agent(self, task: str) -> str:
        self.last_task = task
        return self._agent_key


class FakeAgent:
    """Agent minimal exposant `run(task, model, context)` (contrat AgentLike)."""

    def __init__(self, response: str = "réponse-agent") -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def run(self, task: str, model: str, context: dict[str, Any]) -> Any:
        self.calls.append((task, model, context))
        return {"response": self.response, "suggested_skill": None}


class FakeAgentSupervisor:
    """Double d'AgentSupervisor : capture les args passés par `_run_agent_step`."""

    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self._result = result if result is not None else {"response": "sortie-supervisée"}
        self.last_call: dict[str, Any] | None = None

    def run(
        self,
        agent: Any,
        task: str,
        model: str,
        context: dict[str, Any],
        cancel_fn: Any = None,
    ) -> dict[str, Any]:
        self.last_call = {
            "agent": agent,
            "task": task,
            "model": model,
            "context": context,
            "cancel_fn": cancel_fn,
        }
        return self._result


# ---------------------------------------------------------------------------
# Constructeur — validation DIP
# ---------------------------------------------------------------------------


def _minimal_graph(**overrides: Any) -> AgentGraph:
    defaults: dict[str, Any] = {
        "model_provider": FakeModelProvider(),
        "memory": FakeHabitMemory(),
        "vector_store": FakeVectorStore(),
    }
    defaults.update(overrides)
    return AgentGraph(**defaults)


def test_init_missing_all_required_raises_value_error_listing_them() -> None:
    with pytest.raises(ValueError, match="model_provider.*memory.*vector_store|Dépendances manquantes"):
        AgentGraph(model_provider=None, memory=None, vector_store=None)  # type: ignore[arg-type]


def test_init_missing_one_required_raises_value_error_naming_it() -> None:
    with pytest.raises(ValueError, match="memory"):
        AgentGraph(model_provider=FakeModelProvider(), memory=None, vector_store=FakeVectorStore())  # type: ignore[arg-type]


def test_init_with_only_required_deps_defaults_optional_fields() -> None:
    graph = _minimal_graph()
    assert graph.toolbox is None
    assert graph.agents == {}
    assert graph.router is None
    assert graph.pipeline is None
    assert graph.conversations is None
    assert graph.agent_supervisor is None


def test_init_stores_all_optional_deps_when_provided() -> None:
    supervisor = FakeAgentSupervisor()
    agents = {"dev": FakeAgent()}
    router = FakeRouter()
    graph = _minimal_graph(
        toolbox="fake-toolbox",
        agents=agents,
        router=router,
        pipeline="fake-pipeline",
        conversations="fake-conversations",
        agent_supervisor=supervisor,
    )
    assert graph.toolbox == "fake-toolbox"
    assert graph.agents is agents
    assert graph.router is router
    assert graph.pipeline == "fake-pipeline"
    assert graph.conversations == "fake-conversations"
    assert graph.agent_supervisor is supervisor


# ---------------------------------------------------------------------------
# create_agent_graph — factory
# ---------------------------------------------------------------------------


def test_create_agent_graph_wires_all_args_through() -> None:
    model_provider = FakeModelProvider()
    memory = FakeHabitMemory()
    vector_store = FakeVectorStore()
    supervisor = FakeAgentSupervisor()
    agents = {"dev": FakeAgent()}
    router = FakeRouter()

    graph = create_agent_graph(
        model_provider=model_provider,
        memory=memory,
        vector_store=vector_store,
        toolbox="tb",
        agents=agents,
        router=router,
        pipeline="pl",
        conversations="conv",
        agent_supervisor=supervisor,
    )

    assert isinstance(graph, AgentGraph)
    assert graph.model_provider is model_provider
    assert graph.memory is memory
    assert graph.vector_store is vector_store
    assert graph.toolbox == "tb"
    assert graph.agents is agents
    assert graph.router is router
    assert graph.pipeline == "pl"
    assert graph.conversations == "conv"
    assert graph.agent_supervisor is supervisor


def test_create_agent_graph_raises_on_missing_required_dep() -> None:
    with pytest.raises(ValueError, match="Dépendances manquantes"):
        create_agent_graph(model_provider=None, memory=FakeHabitMemory(), vector_store=FakeVectorStore())


# ---------------------------------------------------------------------------
# _run_agent_step — méthode injectée avec AgentSupervisor mais jamais
# appelée par `run()` (voir note de fin de fichier) : caractérisée seule.
# ---------------------------------------------------------------------------


def test_run_agent_step_without_supervisor_raises_value_error() -> None:
    graph = _minimal_graph(agents={"dev": FakeAgent()})
    with pytest.raises(ValueError, match="AgentSupervisor non injecté"):
        graph._run_agent_step("dev", "fais un truc")


def test_run_agent_step_with_unknown_agent_key_raises_value_error() -> None:
    graph = _minimal_graph(agent_supervisor=FakeAgentSupervisor(), agents={})
    with pytest.raises(ValueError, match="Agent 'dev' introuvable"):
        graph._run_agent_step("dev", "fais un truc")


def test_run_agent_step_resolves_model_when_not_given() -> None:
    supervisor = FakeAgentSupervisor()
    provider = FakeModelProvider(model="qwen2.5")
    graph = _minimal_graph(
        model_provider=provider,
        agent_supervisor=supervisor,
        agents={"dev": FakeAgent()},
    )
    result = graph._run_agent_step("dev", "fais un truc")
    assert result == "sortie-supervisée"
    assert supervisor.last_call is not None
    assert supervisor.last_call["model"] == "qwen2.5"
    assert supervisor.last_call["task"] == "fais un truc"


def test_run_agent_step_uses_explicit_model_without_resolving() -> None:
    supervisor = FakeAgentSupervisor()
    graph = _minimal_graph(agent_supervisor=supervisor, agents={"dev": FakeAgent()})
    graph._run_agent_step("dev", "fais un truc", model="modele-explicite")
    assert supervisor.last_call is not None
    assert supervisor.last_call["model"] == "modele-explicite"


def test_run_agent_step_select_model_failure_propagates_unwrapped_runtime_error() -> None:
    """`_run_agent_step` capture `except ValueError`, mais `select_model` lève
    un `RuntimeError` (services/pipeline_steps.py) : le handler ne matche donc
    jamais et l'exception remonte brute, non enveloppée. Comportement réel
    verrouillé tel quel — pas un fix, une caractérisation (cf. note de fin de
    fichier : signalé comme incohérence à trancher, pas corrigé ici)."""
    graph = _minimal_graph(
        model_provider=FailingModelProvider(),
        agent_supervisor=FakeAgentSupervisor(),
        agents={"dev": FakeAgent()},
    )
    with pytest.raises(RuntimeError, match="Aucun modèle disponible pour l'agent 'dev'"):
        graph._run_agent_step("dev", "fais un truc")


def test_run_agent_step_wraps_value_error_raised_directly_by_provider() -> None:
    """Seul cas où le `except ValueError` de `_run_agent_step` (ligne 82) est
    réellement atteint : le provider lève lui-même un ValueError (et non le
    RuntimeError terminal de `select_model`)."""
    graph = _minimal_graph(
        model_provider=ValueErrorRaisingModelProvider(),
        agent_supervisor=FakeAgentSupervisor(),
        agents={"dev": FakeAgent()},
    )
    with pytest.raises(ValueError, match="Aucun modèle disponible pour 'dev': configuration modèle invalide"):
        graph._run_agent_step("dev", "fais un truc")


def test_run_agent_step_cancel_fn_delegates_to_model_provider() -> None:
    supervisor = FakeAgentSupervisor()
    provider = FakeModelProvider()
    graph = _minimal_graph(
        model_provider=provider,
        agent_supervisor=supervisor,
        agents={"dev": FakeAgent()},
    )
    graph._run_agent_step("dev", "fais un truc")
    assert supervisor.last_call is not None
    supervisor.last_call["cancel_fn"](1234)
    assert provider.cancel_calls == [1234]


def test_run_agent_step_extracts_response_field_only() -> None:
    supervisor = FakeAgentSupervisor(result={"response": "ok", "suggested_skill": "diag"})
    graph = _minimal_graph(agent_supervisor=supervisor, agents={"dev": FakeAgent()})
    result = graph._run_agent_step("dev", "fais un truc")
    assert result == "ok"


def test_run_agent_step_defaults_to_empty_string_when_response_missing() -> None:
    supervisor = FakeAgentSupervisor(result={})
    graph = _minimal_graph(agent_supervisor=supervisor, agents={"dev": FakeAgent()})
    result = graph._run_agent_step("dev", "fais un truc")
    assert result == ""


# ---------------------------------------------------------------------------
# run() — flux complet (5 étapes, avec parallélisation étape 2)
# ---------------------------------------------------------------------------


async def test_run_happy_path_returns_formatted_output_and_indexes_result() -> None:
    agent = FakeAgent(response="voici la réponse")
    router = FakeRouter(agent_key="dev")
    vector_store = FakeVectorStore(search_results=[{"text": "cas similaire"}])
    memory = FakeHabitMemory(habits=[{"habit": "revue de code"}])
    graph = _minimal_graph(
        memory=memory,
        vector_store=vector_store,
        router=router,
        agents={"dev": agent},
    )

    output = await graph.run("écris un test")

    assert output["response"] == "voici la réponse"
    assert output["agent"] == "dev"
    assert output["model"] == "qwen2.5"
    assert output["backend"] == "ollama"
    assert output["error"] is None
    # Étape 1 : select_agent a bien consulté le router avec la tâche.
    assert router.last_task == "écris un test"
    # Étape 2 : retrieve_context a peuplé le contexte avant l'appel agent.
    assert "habits" in output["context"]
    assert "similar_cases" in output["context"]
    # Étape 3 : l'agent a bien reçu le contexte enrichi dans son prompt.
    assert agent.calls, "l'agent aurait dû être appelé"
    # Étape 4 : la réponse finale est indexée dans le vector store.
    assert vector_store.indexed and vector_store.indexed[0][0] == "voici la réponse"


async def test_run_uses_vision_agent_key_when_image_present() -> None:
    agent = FakeAgent(response="je vois une image")
    router = FakeRouter(agent_key="dev")  # ne doit pas être consulté (image prioritaire)
    graph = _minimal_graph(router=router, agents={"vision": agent})

    output = await graph.run("décris ceci", image="base64-fake-image")

    assert output["agent"] == "vision"
    assert router.last_task is None  # select_agent court-circuite le router si image


async def test_run_model_selection_failure_short_circuits_before_query_and_save() -> None:
    agent = FakeAgent()
    vector_store = FakeVectorStore()
    graph = _minimal_graph(
        model_provider=FailingModelProvider(),
        vector_store=vector_store,
        agents={"dev": agent},
    )

    output = await graph.run("une tâche")

    assert output["error"] is not None
    assert "Impossible de sélectionner un modèle" in output["response"]
    # Étapes 3 et 4 jamais atteintes : ni appel agent, ni indexation.
    assert agent.calls == []
    assert vector_store.indexed == []


async def test_run_retrieve_context_exception_is_swallowed_and_run_continues() -> None:
    class ExplodingVectorStore(FakeVectorStore):
        def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
            raise RuntimeError("vector store indisponible")

    agent = FakeAgent(response="quand même une réponse")
    graph = _minimal_graph(vector_store=ExplodingVectorStore(), agents={"dev": agent})

    output = await graph.run("une tâche")

    # L'échec de retrieve_context (capturé dans pipeline_steps) ne doit pas
    # empêcher la suite du run : le contexte retombe à {} mais l'agent tourne.
    assert output["error"] is None
    assert output["response"] == "quand même une réponse"


async def test_run_conversation_id_and_image_are_carried_in_initial_state() -> None:
    graph = _minimal_graph(agents={"dev": FakeAgent()}, router=FakeRouter())
    output = await graph.run("une tâche", image=None, conversation_id="conv-42")
    # conversation_id n'apparaît pas dans format_output (non exposé) — on
    # vérifie seulement qu'aucune erreur n'est levée par sa présence dans state.
    assert output["error"] is None


async def test_run_with_no_matching_agent_reports_agent_error_via_query_model() -> None:
    router = FakeRouter(agent_key="inconnu")
    graph = _minimal_graph(router=router, agents={"dev": FakeAgent()})

    output = await graph.run("une tâche")

    assert output["agent"] == "inconnu"
    assert output["error"] == "Agent 'inconnu' introuvable"
    assert "n'est pas disponible" in output["response"]


# ---------------------------------------------------------------------------
# Notes d'audit (Lot 2), non corrigées ici — signalées pour décision produit :
#
# 1. `_run_agent_step` et `agent_supervisor` sont injectés dans
#    AgentGraph.__init__ mais `run()` ne les appelle jamais — `query_model`
#    (services/pipeline_steps.py) appelle `agent.run(...)` directement, sans
#    passer par AgentSupervisor ni son timeout wall-clock.
# 2. Dans `_run_agent_step`, le `except ValueError` autour de `select_model`
#    ne matche presque jamais en pratique : l'échec normal de `select_model`
#    (aucun modèle disponible) lève `RuntimeError` (services/pipeline_steps.py:79),
#    pas `ValueError`, et remonte donc non enveloppé
#    (cf. test_run_agent_step_select_model_failure_propagates_unwrapped_runtime_error).
#    Le handler n'est atteint que si le `ModelRegistryPort` injecté lève lui-même
#    un `ValueError` (cf. test_run_agent_step_wraps_value_error_raised_directly_by_provider) —
#    un cas non documenté dans le contrat `ModelRegistryPort`.
# ---------------------------------------------------------------------------
