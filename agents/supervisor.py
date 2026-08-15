"""AgentSupervisor — Garde-fou d'exécution par agent (wall-clock timeout).

Encadre l'appel ``agent.run`` d'un timeout wall-clock configurable. Si l'agent
(prompt + toolbox + appel LLM) dépasse le délai, une réponse d'erreur
structurée est retournée au lieu de bloquer indéfiniment le pipeline.

Pourquoi un thread manuel et non ``concurrent.futures`` ?
-------------------------------------------------------
Les threads Python ne sont **pas** interruptibles : ``Future.cancel()`` ne
stoppe pas un thread déjà démarré. Le pattern ``Thread`` + ``join(timeout)``
est donc requis pour pouvoir invoquer ``cancel_fn`` (fermeture du client HTTP
Ollama) et éviter un thread « zombie » qui continuerait de consommer CPU/GPU
après le délai.

Sécurité mémoire
----------------
``result`` et ``error`` sont écrits par le worker puis lus par le thread
appelant **après** ``join()`` : ``join`` établit une relation *happens-before*,
la lecture est donc sûre sans verrou.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Protocol

from config.constants import AGENT_TIMEOUT_SECONDS

_logger = logging.getLogger("jarvis.agents.supervisor")

# Type d'un callback d'annulation best-effort (annulation de la requête du
# worker thread identifié par son identifiant).
CancelFn = Callable[[int], None]


# ---------------------------------------------------------------------------
# Contrat minimal de l'agent supervisé (ISP : seule la méthode exécutée).
# ---------------------------------------------------------------------------

class AgentLike(Protocol):
    """Tout objet exposant ``run(task, model, context)`` peut être supervisé."""

    def run(self, task: str, model: str, context: dict[str, Any]) -> Any: ...


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class AgentSupervisor:
    """Exécute ``run()`` d'un agent sous garde-fou de timeout wall-clock."""

    def __init__(self, timeout: int | None = None) -> None:
        # ``is None`` et non ``or`` : un ``timeout`` explicite (même faible)
        # doit être respecté ; seul l'absence (None) retombe sur le défaut.
        resolved = AGENT_TIMEOUT_SECONDS if timeout is None else timeout
        if resolved <= 0:
            raise ValueError(f"timeout must be > 0, got {resolved}")
        self._timeout: int = resolved

    def run(
        self,
        agent: AgentLike,
        task: str,
        model: str,
        context: dict[str, Any],
        cancel_fn: CancelFn | None = None,
    ) -> dict[str, Any]:
        """Exécute ``agent.run`` dans un thread ; résultat ou erreur timeout.

        Un ``stop_event`` est transmis dans le contexte de l'agent.
        Si le timeout expire, l'événement est déclenché pour demander à
        l'agent de s'arrêter le plus rapidement possible.
        """
        result: dict[str, Any] | None = None
        error: BaseException | None = None

        stop_event = threading.Event()

        def _target() -> None:
            nonlocal result, error
            ctx = {**context, "_stop_event": stop_event}
            try:
                result = agent.run(task, model, ctx)
            except BaseException as exc:  # propagé proprement ci-dessous
                error = exc

        worker = threading.Thread(target=_target, daemon=True)
        worker.start()
        worker.join(self._timeout)

        if worker.is_alive():
            stop_event.set()  # SIGNALER AU WORKER
            return self._on_timeout(agent, model, cancel_fn, worker.ident)

        if error is not None:
            raise error

        # Fail-Fast : un worker terminé sans erreur DOIT avoir produit un
        # résultat. ``None`` signifie que l'agent a violé son contrat de
        # retour (``run() -> AgentRunResult``). On lève au point de défaillance
        # plutôt que de retourner ``{}``, qui produirait un KeyError opaque
        # chez le consommateur (``result["response"]``).
        if result is None:
            raise RuntimeError(
                f"Agent {_agent_name(agent)} a terminé sans résultat ni erreur (contrat run() violé : retour None)"
            )
        return result

    # ------------------------------------------------------------------
    # Gestion du timeout
    # ------------------------------------------------------------------

    def _on_timeout(
        self,
        agent: AgentLike,
        model: str,
        cancel_fn: CancelFn | None,
        worker_ident: int | None,
    ) -> dict[str, Any]:
        """Construit la réponse de timeout et tente l'annulation best-effort."""
        name = _agent_name(agent)
        _logger.warning("Agent %s dépasse le timeout de %ds", name, self._timeout)
        self._try_cancel(cancel_fn, name, worker_ident)
        return self._timeout_result(name, model)

    def _try_cancel(self, cancel_fn: CancelFn | None, name: str, worker_ident: int | None) -> None:
        """Invoque ``cancel_fn`` avec l'ident du worker, sans jamais propager d'exception."""
        if cancel_fn is None or worker_ident is None:
            return
        try:
            cancel_fn(worker_ident)
        except Exception:  # noqa: BLE001 - annulation best-effort
            _logger.warning("Agent %s : échec de cancel_fn au timeout", name, exc_info=True)

    def _timeout_result(self, name: str, model: str) -> dict[str, Any]:
        """Réponse structurée retournée quand l'agent dépasse le délai.

        → voir BACKLOG « Tickets TODO → BACKLOG (Lot 5.5) » pour le refacto
        vers un union type ``RunOutcome``.
        """
        return {
            "response": f"[Timeout] l'agent n'a pas répondu sous {self._timeout}s",
            "agent": name,
            "model": model,
            "timeout": True,
        }


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def _agent_name(agent: AgentLike) -> str:
    """Nom lisible de l'agent pour les logs (lecture défensive).

    Priorité : ``name`` explicite > ``profile_key`` (contrat uniforme
    ``BaseAgent.profile_key``, Lot H1 — remplace les deux anciennes
    conventions divergentes ``_profile_key``/``PROFILE_KEY``) > nom de
    classe en dernier recours (agent duck-typé sans l'un ni l'autre).
    ``getattr`` reste défensif : ``AgentLike`` n'exige que ``run``.
    """
    name = getattr(agent, "name", None)
    if name:
        return str(name)
    profile = getattr(agent, "profile_key", None)
    return str(profile) if profile else type(agent).__name__


__all__ = ["AgentSupervisor", "CancelFn"]