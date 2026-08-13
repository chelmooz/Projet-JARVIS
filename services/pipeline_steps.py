"""Pipeline Steps — Étapes unitaires de l'orchestration séquentielle."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from config.agent_profiles import model_for_agent

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


def execute_pipeline_step(
    state: dict[str, Any],
    step: Any,  # PipeStep
    task: str,
    agent_runner: Any = None,
    inference: Any = None,
    model_selector: Any = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Exécute une étape de pipeline avec gestion des réessais.

    Cette fonction implémente la logique d'exécution d'étape qui était auparavant
    dans PipelineService._execute_with_retry et _execute_step.

    Args:
        state: Dictionnaire d'état contenant au moins :
              - task: la tâche originale
              - context: dictionnaire de contexte pour l'étape
              - results: liste des résultats des étapes précédentes
              - error: erreur éventuelle (doit être None pour continuer)
        step: L'étape à exécuter (doit avoir name, agent_key, prompt_template, on_error)
        task: La tâche originale (pour le templating du prompt)
        agent_runner: Le runner d'agent (peut être None)
        inference: Le service d'inférence (peut être None)
        model_selector: Sélecteur de modèle (peut être None)
        max_retries: Nombre maximal de réessais par étape

    Returns:
        L'état mis à jour avec les résultats de l'étape ou une erreur
    """
    # Si une erreur a déjà eu lieu et que l'étape ne doit pas être ignorée, on skip
    if state.get("error") is not None and step.on_error != "skip":
        return state

    # Si le contexte n'existe pas encore, on l'initialise
    if "context" not in state:
        state["context"] = {}

    # Si les résultats n'existent pas encore, on les initialise
    if "results" not in state:
        state["results"] = []

    # Préparer le prompt pour cette étape
    prompt = step.prompt_template.format(task=task, **state["context"])

    # Variable pour stocker le résultat de la tentative réussie
    successful_result = None
    successful_error = None

    # Boucle de réessais
    for attempt in range(max_retries + 1):
        try:
            # Essayer d'exécuter l'étape
            result = None
            error = None

            # Essayer avec l'agent_runner d'abord (si disponible et si l'étape spécifie une clé d'agent)
            if agent_runner is not None and step.agent_key:
                # TODO: Implémenter l'appel à l'agent_runner avec gestion du modèle
                # Pour l'instant, on simule une réponse en appelant l'agent_runner comme une fonction
                # TODO: Ceci devrait être remplacé par l'appel approprié selon l'interface de agent_runner
                result = agent_runner(step.agent_key, prompt) if callable(agent_runner) else str(agent_runner)
            # Sinon, essayer avec l'inférence
            elif inference is not None:
                # Appeler le service d'inférence
                raw_result = inference.query(prompt, None)  # TODO: passer le modèle approprié
                # Extraire la réponse du résultat brut
                if hasattr(raw_result, "data") and isinstance(raw_result.data, dict):
                    result = str(raw_result.data.get("response", str(raw_result)))
                elif isinstance(raw_result, dict):
                    result = str(raw_result.get("response", str(raw_result)))
                else:
                    result = str(raw_result)
            else:
                error = "Aucun agent_runner ni inference configuré"

            # Si on a un résultat sans erreur, on sort de la boucle de réessais
            if error is None:
                successful_result = result
                successful_error = None
                break
            else:
                # Sinon, on mémorise l'erreur et on continue si on peut encore réessayer
                successful_error = error
                if attempt >= max_retries:
                    # On a épuisé nos réessais
                    break
                # Sinon, on continue à la prochaine itération

        except Exception as e:
            # Exception inattendue lors de l'exécution
            successful_error = str(e)
            if attempt >= max_retries:
                break

    # Traiter le résultat final
    if successful_error is not None:
        # Échec après tous les réessais
        state["error"] = successful_error
        # Ajouter un résultat d'échec à la liste
        state["results"].append(
            {
                "step": step.name,
                "agent": step.agent_key,
                "response": None,
                "error": successful_error,
            }
        )
    else:
        # Succès
        # Ajouter un résultat de succès à la liste
        state["results"].append(
            {
                "step": step.name,
                "agent": step.agent_key,
                "response": successful_result,
                "error": None,
            }
        )
        # Mettre à jour le contexte avec le résultat de cette étape
        state["context"][step.name] = successful_result

    return state
