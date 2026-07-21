"""AgentSupervisor — Garde-fou d'exécution par agent (M23c).

Encadre l'appel `agent.run` avec un timeout wall-clock configurables. Si l'agent
(prompt + toolbox + appel LLM) dépasse le délai, une réponse d'erreur structurée est
retournée au lieu de bloquer indéfiniment le pipeline.
"""
import logging
import threading

from config.constants import AGENT_TIMEOUT_SECONDS

_logger = logging.getLogger("jarvis.agents.supervisor")


class AgentSupervisor:
    """Exécute run() d'un agent avec un garde-fou de timeout (wall-clock)."""

    def __init__(self, timeout: int | None = None):
        self._timeout = timeout or AGENT_TIMEOUT_SECONDS

    def run(self, agent, task: str, model: str, context: dict, cancel_fn=None) -> dict:
        """Exécute agent.run dans un thread ; renvoie le résultat ou une erreur timeout.

        `cancel_fn` (optionnel) est appelé au timeout pour annuler la requête sous-
        jacente (ex. fermer le client HTTP Ollama) et éviter un thread daemon 'zombie'
        qui continuerait de consommer CPU/GPU après le délai.
        """
        result_box: dict = {}
        error_box: dict = {}

        def _target():
            try:
                result_box["value"] = agent.run(task, model, context)
            except Exception as e:  # noqa: BLE001 - propagé proprement plus bas
                error_box["value"] = e

        worker = threading.Thread(target=_target, daemon=True)
        worker.start()
        worker.join(self._timeout)

        if worker.is_alive():
            profile = getattr(agent, "_profile_key", "?")
            _logger.warning("Agent %s depasse le timeout %ds", profile, self._timeout)
            if cancel_fn is not None:
                try:
                    cancel_fn()
                except Exception:  # noqa: BLE001 - annulation best-effort
                    _logger.warning("Agent %s : echec cancel_fn au timeout", profile, exc_info=True)
            return {
                "response": f"[Timeout] l'agent n'a pas repondu sous {self._timeout}s",
                "agent": profile,
                "model": model,
                "timeout": True,
            }

        if "value" in error_box:
            raise error_box["value"]

        return result_box.get("value", {})
