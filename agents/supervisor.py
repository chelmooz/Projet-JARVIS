"""AgentSupervisor — Garde-fou d'exécution par agent (wall-clock timeout).

Encadre l'appel ``agent.run`` d'un timeout wall-clock configurable. Si l'agent
(prompt + toolbox + appel LLM) dépasse le délai, une réponse d'erreur
structurée est retournée au lieu de bloquer indéfiniment le pipeline.

Pourquoi un thread manuel et non ``concurrent.futures`` ?
--------------------------------------------------------
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
from typing import Any, Callable, Protocol

from config.constants import AGENT_TIMEOUT_SECONDS

_logger = logging.getLogger("jarvis.agents.supervisor")

# Type d'un callback d'annulation best-effort (fermeture du client sous-jacent).
CancelFn = Callable[[], None]


# ---------------------------------------------------------------------------
# Contrat minimal de l'agent supervisé (ISP : seule la méthode exécutée).
# ---------------------------------------------------------------------------

class _AgentLike(Protocol):
    """Tout objet exposant ``run(task, model, context)`` peut être supervisé."""

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]: ...


def _agent_name(agent: _AgentLike) -> str:
    """Nom lisible de l'agent pour les logs (lecture défensive).

    Les conventions de nommage divergent encore dans la hiérarchie
    (``_profile_key`` en instance pour Generic/Vision, ``PROFILE_KEY`` en
    classe pour Cyber). Ce helper centralise la connaissance de ces
    conventions en un point.

    TODO(refacto-SOLID): ajouter une propriété publique ``name`` sur
    ``BaseAgent`` (1 re-commit) et supprimer ce getattr multi-conventions.
    """
    name = getattr(agent, "name", None)
    if name:
        return str(name)
    profile = getattr(agent, "_profile_key", None) or getattr(agent, "PROFILE_KEY", None)
    return str(profile) if profile else type(agent).__name__


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
        agent: _AgentLike,
        task: str,
        model: str,
        context: dict[str, Any],
        cancel_fn: CancelFn | None = None,
    ) -> dict[str, Any]:
        """Exécute ``agent.run`` dans un thread ; résultat ou erreur timeout.

        ``cancel_fn`` (optionnel) est appelé au timeout pour annuler la requête
        sous-jacente (ex. fermer le client HTTP Ollama).
        """
        result: dict[str, Any] | None = None
        error: BaseException | None = None

        def _target() -> None:
            nonlocal result, error
            try:
                result = agent.run(task, model, context)
            except BaseException as exc:  # propagé proprement ci-dessous
                error = exc

        worker = threading.Thread(target=_target, daemon=True)
        worker.start()
        worker.join(self._timeout)

        if worker.is_alive():
            return self._on_timeout(agent, model, cancel_fn)

        if error is not None:
            raise error

        return result if result is not None else {}

    # ------------------------------------------------------------------
    # Gestion du timeout
    # ------------------------------------------------------------------

    def _on_timeout(
        self,
        agent: _AgentLike,
        model: str,
        cancel_fn: CancelFn | None,
    ) -> dict[str, Any]:
        """Construit la réponse de timeout et tente l'annulation best-effort."""
        name = _agent_name(agent)
        _logger.warning("Agent %s dépasse le timeout de %ds", name, self._timeout)
        self._try_cancel(cancel_fn, name)
        return self._timeout_result(name, model)

    def _try_cancel(self, cancel_fn: CancelFn | None, name: str) -> None:
        """Invoque ``cancel_fn`` sans jamais propager d'exception."""
        if cancel_fn is None:
            return
        try:
            cancel_fn()
        except Exception:  # noqa: BLE001 - annulation best-effort
            _logger.warning("Agent %s : échec de cancel_fn au timeout", name, exc_info=True)

    def _timeout_result(self, name: str, model: str) -> dict[str, Any]:
        """Réponse structurée retournée quand l'agent dépasse le délai.

        TODO(refacto-SOLID): modéliser ce cas par un union type
        ``RunOutcome = AgentRunResult | TimeoutResult`` (re-commit models/base)
        au lieu d'un champ de contrôle ``timeout`` ajouté au dict nominal.
        """
        return {
            "response": f"[Timeout] l'agent n'a pas répondu sous {self._timeout}s",
            "agent": name,
            "model": model,
            "timeout": True,
        }


__all__ = ["AgentSupervisor", "CancelFn"]
