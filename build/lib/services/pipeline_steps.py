"""Pipeline steps — 5 fonctions autonomes pour le pipeline AgentGraph.

Remplace AgentSelectorService, ContextRetrieverService, ModelQueryService,
ResultPersistenceService et OutputFormatterService par 5 fonctions pures.
"""

from agents.supervisor import AgentSupervisor
from services import selector

_supervisor = AgentSupervisor()


def select_agent(state: dict, router) -> dict:
    state["agent_key"] = "vision" if state.get("image") else router.select_agent(state["task"])
    return state


def select_model(agent_key: str, image: str | None, inference) -> str:
    if image:
        return selector.select_vision_model(inference) or ""
    if inference and inference.first_available() is None:
        return ""
    return selector.select_model(agent_key, inference)


def retrieve_context(state: dict, memory, vector_store, inference) -> dict:
    has_task = bool(state["task"] and inference and inference.first_available() is not None)
    similar = vector_store.search(state["task"], top_k=5) if has_task else []
    state["context"] = {
        "recent_tasks": memory.get_habits(),
        "similar_cases": similar,
    }
    return state


def _validate_query(model: str, task: str) -> str | None:
    """Retourne le message d'erreur si la requête est invalide, sinon None."""
    if not model:
        return "Aucun modele disponible"
    if not task:
        return "Tache vide"
    return None


def _build_query_context(state: dict, toolbox) -> dict:
    """Contexte d'exécution : habitudes + résultats d'outils (si pertinents)."""
    context = dict(state.get("context", {}))
    if not state.get("image") and toolbox.is_enabled():
        tool_results = toolbox.auto_execute(state["task"])
        if tool_results:
            context["tool_results"] = tool_results
    return context


def query_model(state: dict, inference, agents, toolbox, select_model_fn) -> dict:
    agent_key = state.get("agent_key", "dev")
    model = select_model_fn(agent_key, state.get("image"), inference)
    if error := _validate_query(model, state["task"]):
        state["error"] = error
        return state
    result = _supervisor.run(
        agents[agent_key], state["task"], model, _build_query_context(state, toolbox)
    )
    state["model"] = result.get("model", model)
    state["response"] = result.get("response", "")
    state["suggested_skill"] = result.get("suggested_skill")
    state["result"] = result
    return state


def save_results(state: dict, memory, vector_store) -> dict:
    """Persiste les habitudes et l'index vectoriel d'une réponse.

    La persistance de la conversation (user + assistant) est déléguée à la
    couche transport (route `_save_conv`), afin d'éviter une double écriture
    (bug #1 : `save_results` + la route écrivaient tous les deux → messages
    en double dans l'historique).
    """
    if not state.get("response"):
        return state
    result_meta = state.get("result") or {}
    memory.update_habits({"task": state["task"], "agent": state["agent_key"]})
    vector_store.index(state["task"], metadata=result_meta)
    vector_store.index(state["response"], metadata=result_meta)
    vector_store.vectorize_pending()
    return state


def format_output(state: dict) -> dict:
    result = state.get("result") or {}
    error = state.get("error")
    response = error or state.get("response", "")
    return {
        "response": response,
        "agent": state.get("agent_key") or result.get("agent_key", ""),
        "agent_key": state.get("agent_key", ""),
        "model": state.get("model") or result.get("model", ""),
        "backend": result.get("backend", "ollama"),
        "suggested_skill": state.get("suggested_skill") or result.get("suggested_skill"),
    }
