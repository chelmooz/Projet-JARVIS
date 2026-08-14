"""Pipeline Steps — Étapes unitaires de l'orchestration séquentielle."""

from __future__ import annotations

import inspect
import logging
import time
from collections.abc import Mapping
from typing import Any

from config.agent_profiles import model_for_agent

_logger = logging.getLogger("jarvis.pipeline_steps")

RETRY_DELAY = 0.5
MAX_ERROR_LENGTH = 200


def _should_retry(step: Any, attempt: int, max_retries: int) -> bool:
    """Retry conditionnel (parité production pipeline.py) : on_error == "retry"."""
    return step.on_error == "retry" and attempt < max_retries


def _wait_before_retry(attempt: int, max_retries: int, step_name: str) -> None:
    delay = RETRY_DELAY * (attempt + 1)
    _logger.warning("Retry %d/%d pour '%s'", attempt + 1, max_retries, step_name)
    time.sleep(delay)


class NonCallableRunnerError(Exception):
    """Levée quand ``agent_runner`` n'est pas callable (attr échec d'étape)."""


def _runner_supports_model(runner: Any) -> bool:
    """Vérifie si le runner accepte un 3e argument 'model' (parité pipeline.py)."""
    try:
        sig = inspect.signature(runner)
        return len(sig.parameters) >= 3
    except (ValueError, TypeError):
        return False


def select_agent(state: dict[str, Any], router: Any) -> dict[str, Any]:
    if state.get("image"):
        state["agent_key"] = "vision"
    elif router is not None:
        state["agent_key"] = router.select_agent(state.get("task", ""))
    else:
        state["agent_key"] = "dev"
    return state


def select_model(agent_key: str, model: str | None, provider: Any) -> str:
    """Résout le modèle à utiliser pour ``agent_key``.

    Ordre de priorité : modèle explicite (déjà choisi par l'utilisateur) >
    modèle configuré pour cet agent dans agent_profiles.json (résolu contre
    les modèles réellement présents sur Ollama) > premier modèle disponible
    capable de génération de texte, en dernier recours.

    Note : ``resolve_model()`` attend un nom de modèle (ex. "qwen2.5"), pas
    une clé d'agent (ex. "techlead") — d'où le passage par
    ``model_for_agent()`` plutôt qu'un ``resolve(agent_key)`` direct, qui ne
    matcherait jamais rien.
    """
    if model:
        return model
    resolve = getattr(provider, "resolve_model", None)
    if resolve is not None:
        configured = model_for_agent(agent_key)
        resolved = resolve(configured) if configured else None
        if resolved:
            return str(resolved)
    first = getattr(provider, "first_available", None)
    if first is not None:
        available = first()
        if available:
            return str(available)
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


def query_model(
    state: dict[str, Any],
    provider: Any,
    agents: Mapping[str, object],
    toolbox: Any,
    model_selector: Any,
) -> dict[str, Any]:
    agent_key = state.get("agent_key", "dev")
    agent = agents.get(agent_key)
    if agent is None:
        state["error"] = f"Agent '{agent_key}' introuvable"
        state["response"] = f"Désolé, l'agent '{agent_key}' n'est pas disponible."
        return state
    model = model_selector(agent_key, state.get("model"), provider)
    state["model"] = model
    task = state.get("task", "")
    context = state.setdefault("context", {})
    if not task:
        state["error"] = "Tâche vide — rien à exécuter"
        state["response"] = "Je n'ai pas reçu de tâche à exécuter."
        return state
    prompt = task
    if context:
        context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
        prompt = f"Contexte:\n{context_str}\n\nTâche: {task}"
    if toolbox is not None:
        auto = getattr(toolbox, "auto_execute", None)
        if auto is not None:
            try:
                context["tool_results"] = auto(task) or {}
            except Exception as e:
                _logger.warning("Toolbox indisponible : %s", e)
                context["tool_results"] = {}
    try:
        if hasattr(agent, "run"):
            result = agent.run(prompt, model=model, context=context)
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
