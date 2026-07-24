"""Pipeline Steps — Étapes unitaires de l'orchestration séquentielle."""
from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger("jarvis.pipeline_steps")


def select_agent(state: dict[str, Any], router: Any) -> dict[str, Any]:
    if state.get("image"):
        state["agent_key"] = "vision"
    elif router is not None:
        state["agent_key"] = router.select_agent(state.get("task", ""))
    else:
        state["agent_key"] = "dev"
    return state


def select_model(agent_key: str, model: str | None, provider: Any) -> str:
    if model:
        return model
    resolve = getattr(provider, "resolve_model", None)
    if resolve is not None:
        resolved = resolve(agent_key)
        if resolved:
            return resolved
    first = getattr(provider, "first_available", None)
    if first is not None:
        available = first()
        if available:
            return available
    raise RuntimeError(f"Aucun modèle disponible pour l'agent '{agent_key}'")


def retrieve_context(state: dict[str, Any], memory: Any, vector_store: Any, provider: Any) -> dict[str, Any]:
    context: dict[str, Any] = {}
    if memory is not None:
        try:
            habits = memory.get_habits(limit=5)
            if habits:
                context["habits"] = habits
        except Exception as e:
            _logger.debug("Mémoire indisponible : %s", e)
    if vector_store is not None:
        try:
            results = vector_store.search(state.get("task", ""), top_k=3)
            if results:
                context["similar_cases"] = results
        except Exception as e:
            _logger.debug("Vector store indisponible : %s", e)
    state["context"] = context
    return state


def query_model(state: dict[str, Any], provider: Any, agents: dict[str, object], toolbox: Any, model_selector: Any) -> dict[str, Any]:
    agent_key = state.get("agent_key", "dev")
    agent = agents.get(agent_key)
    if agent is None:
        state["error"] = f"Agent '{agent_key}' introuvable"
        state["response"] = f"Désolé, l'agent '{agent_key}' n'est pas disponible."
        return state
    model = model_selector(agent_key, state.get("model"), provider)
    task = state.get("task", "")
    context = state.get("context", {})
    if not task:
        state["error"] = "Tâche vide — rien à exécuter"
        state["response"] = "Je n'ai pas reçu de tâche à exécuter."
        return state
    prompt = task
    if context:
        context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        prompt = f"Contexte:\n{context_str}\n\nTâche: {task}"
    try:
        if hasattr(agent, "run"):
            result = agent.run(prompt, model=model, context=state.get("context", {}))
        elif hasattr(agent, "query"):
            result = agent.query(prompt, model=model)
        else:
            result = {"response": str(agent)}
        if isinstance(result, dict):
            state["response"] = result.get("response", str(result))
            state["suggested_skill"] = result.get("suggested_skill")
            state["result"] = result
        else:
            state["response"] = str(result)
    except Exception as e:
        _logger.error("Erreur agent '%s' : %s", agent_key, e)
        state["error"] = str(e)
        state["response"] = f"Une erreur est survenue : {e}"
    return state


def save_results(state: dict[str, Any], memory: Any, vector_store: Any) -> dict[str, Any]:
    response = state.get("response", "")
    if not response:
        return state
    if vector_store is not None:
        try:
            vector_store.index(response, metadata={"source": "agent_response"})
        except Exception as e:
            _logger.debug("Indexation vectorielle échouée : %s", e)
    return state


def format_output(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "response": state.get("response", ""),
        "agent": state.get("agent_key", ""),
        "model": state.get("model", ""),
        "backend": state.get("backend", "ollama"),
        "error": state.get("error"),
        "suggested_skill": state.get("suggested_skill"),
        "context": state.get("context", {}),
    }


__all__ = [
    "select_agent",
    "select_model",
    "retrieve_context",
    "query_model",
    "save_results",
    "format_output",
]
