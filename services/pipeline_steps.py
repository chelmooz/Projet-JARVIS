"""Pipeline steps — 5 fonctions autonomes pour le pipeline AgentGraph.

Remplace AgentSelectorService, ContextRetrieverService, ModelQueryService,
ResultPersistenceService et OutputFormatterService par 5 fonctions pures.
"""
from __future__ import annotations

from typing import Any, Callable

from agents.supervisor import AgentSupervisor
from services import selector

_supervisor = AgentSupervisor()


def select_agent(state: dict[str, Any], router: Any) -> dict[str, Any]:
    """Sélectionne l'agent cible (vision si image, sinon via le routeur)."""
    state["agent_key"] = "vision" if state.get("image") else router.select_agent(state.get("task", ""))
    return state


def select_model(agent_key: str, image: str | None, inference: Any) -> str:
    """Sélectionne le modèle approprié (vision ou texte)."""
    if image:
        return selector.select_vision_model(inference) or ""
    if inference and inference.first_available() is None:
        return ""
    return selector.select_model(agent_key, inference)


def retrieve_context(
    state: dict[str, Any], memory: Any, vector_store: Any, inference: Any
) -> dict[str, Any]:
    """Construit le contexte de la requête (habitudes + cas similaires)."""
    task = state.get("task", "")
    has_task = bool(task and inference and inference.first_available() is not None)
    similar = vector_store.search(task, top_k=5) if has_task else []
    
    state["context"] = {
        "recent_tasks": memory.get_habits() if memory else [],
        "similar_cases": similar,
    }
    return state


def _validate_query(model: str, task: str) -> str | None:
    """Retourne le message d'erreur si la requête est invalide, sinon None."""
    if not model:
        return "Aucun modèle disponible"
    if not task:
        return "Tâche vide"
    return None


def _build_query_context(state: dict[str, Any], toolbox: Any) -> dict[str, Any]:
    """Contexte d'exécution : habitudes + résultats d'outils (si pertinents)."""
    context = dict(state.get("context", {}))
    if not state.get("image") and toolbox and toolbox.is_enabled():
        tool_results = toolbox.auto_execute(state.get("task", ""))
        if tool_results:
            context["tool_results"] = tool_results
    return context


def query_model(
    state: dict[str, Any],
    inference: Any,
    agents: dict[str, Any],
    toolbox: Any,
    select_model_fn: Callable[[str, str | None, Any], str],
) -> dict[str, Any]:
    """Interroge le modèle via l'agent sélectionné et le superviseur."""
    agent_key = state.get("agent_key", "dev")
    model = select_model_fn(agent_key, state.get("image"), inference)
    
    if error := _validate_query(model, state.get("task", "")):
        state["error"] = error
        return state
        
    agent = agents.get(agent_key)
    if not agent:
        state["error"] = f"Agent '{agent_key}' introuvable"
        return state

    result = _supervisor.run(
        agent, state.get("task", ""), model, _build_query_context(state, toolbox)
    )
    state["model"] = result.get("model", model)
    state["response"] = result.get("response", "")
    state["suggested_skill"] = result.get("suggested_skill")
    state["result"] = result
    return state


def save_results(state: dict[str, Any], memory: Any, vector_store: Any) -> dict[str, Any]:
    """Persiste les habitudes et l'index vectoriel d'une réponse.

    La persistance de la conversation (user + assistant) est déléguée à la
    couche transport (route `_save_conv`), afin d'éviter une double écriture
    (bug #1 : `save_results` + la route écrivaient tous les deux → messages
    en double dans l'historique).
    """
    if not state.get("response"):
        return state
        
    result_meta = state.get("result") or {}
    task = state.get("task", "")
    agent_key = state.get("agent_key", "")
    
    if memory:
        memory.update_habits({"task": task, "agent": agent_key})
    if vector_store:
        vector_store.index(task, metadata=result_meta)
        vector_store.index(state["response"], metadata=result_meta)
        vector_store.vectorize_pending()
        
    return state


def format_output(state: dict[str, Any]) -> dict[str, Any]:
    """Formate la réponse finale pour l'API."""
    result = state.get("result") or {}
    error = state.get("error")
    response = error or state.get("response", "")
    
    return {
        "response": response,
        "agent": state.get("agent_key") or result.get("agent", ""),
        "agent_key": state.get("agent_key", ""),
        "model": state.get("model") or result.get("model", ""),
        "backend": result.get("backend", "ollama"),
        "suggested_skill": state.get("suggested_skill") or result.get("suggested_skill"),
    }


__all__ = [
    "select_agent",
    "select_model",
    "retrieve_context",
    "query_model",
    "save_results",
    "format_output",
]
