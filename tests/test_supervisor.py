"""Tests de caractérisation et de non-régression pour ``agents.supervisor``.

Avant ce fichier, ``AgentSupervisor`` et ``_agent_name`` avaient 0% de
couverture (aucun test ne les exerçait). Ces tests fixent le comportement
observé avant le refactor H1 (Lot H) puis servent de filet pour la
factorisation de la convention de nommage du profil (``_profile_key`` vs
``PROFILE_KEY``) en une propriété unique ``profile_key``.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from agents.supervisor import AgentSupervisor, _agent_name

# ---------------------------------------------------------------------------
# Doubles d'agents
# ---------------------------------------------------------------------------


class _FastAgent:
    """Agent qui répond immédiatement."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self._response = response if response is not None else {"response": "ok", "agent": "fast"}

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
        return self._response


class _SlowAgent:
    """Agent qui dépasse volontairement le timeout."""

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
        time.sleep(5)
        return {"response": "trop tard"}


class _CrashingAgent:
    """Agent dont ``run`` lève une exception."""

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("boom")


class _NoneAgent:
    """Agent qui viole le contrat en retournant None."""

    def run(self, task: str, model: str, context: dict[str, Any]) -> Any:
        return None


class _NamedAgent:
    """Agent exposant un attribut ``name`` (priorité la plus haute dans _agent_name)."""

    name = "orchestrateur"

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"response": "ok"}


class _ProfileKeyAgent:
    """Agent exposant le contrat uniforme ``profile_key`` (Lot H1)."""

    profile_key = "techlead"

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"response": "ok"}


class _BareAgent:
    """Agent sans ``name`` ni convention de profil : repli sur le nom de classe."""

    def run(self, task: str, model: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"response": "ok"}


# ---------------------------------------------------------------------------
# _agent_name — caractérisation des 4 conventions
# ---------------------------------------------------------------------------


def test_agent_name_prefers_name_attribute() -> None:
    assert _agent_name(_NamedAgent()) == "orchestrateur"


def test_agent_name_reads_profile_key() -> None:
    assert _agent_name(_ProfileKeyAgent()) == "techlead"


def test_agent_name_falls_back_to_class_name() -> None:
    assert _agent_name(_BareAgent()) == "_BareAgent"


def test_agent_name_on_real_generic_agent_reads_profile_key() -> None:
    """Filet d'intégration : GenericAgent expose bien profile_key (Lot H1)."""
    from agents.generic import GenericAgent

    agent = GenericAgent(model_provider=_FastAgent(), profile_key="hardware")
    assert _agent_name(agent) == "hardware"


def test_agent_name_on_real_cyber_agent_reads_profile_key() -> None:
    """Filet d'intégration : CyberAgent expose bien profile_key (Lot H1)."""
    from agents.cyber import CyberAgent

    agent = CyberAgent(model_provider=_FastAgent())
    assert _agent_name(agent) == "datasecu"


# ---------------------------------------------------------------------------
# AgentSupervisor.run — comportements existants
# ---------------------------------------------------------------------------


def test_run_returns_agent_result_on_success() -> None:
    supervisor = AgentSupervisor(timeout=5)
    result = supervisor.run(_FastAgent(), "task", "model", {})
    assert result == {"response": "ok", "agent": "fast"}


def test_run_raises_propagated_error() -> None:
    supervisor = AgentSupervisor(timeout=5)
    with pytest.raises(ValueError, match="boom"):
        supervisor.run(_CrashingAgent(), "task", "model", {})


def test_run_raises_on_none_result_contract_violation() -> None:
    supervisor = AgentSupervisor(timeout=5)
    with pytest.raises(RuntimeError, match="contrat run.. violé"):
        supervisor.run(_NoneAgent(), "task", "model", {})


def test_run_returns_timeout_result_when_agent_too_slow() -> None:
    supervisor = AgentSupervisor(timeout=1)
    result = supervisor.run(_SlowAgent(), "task", "model-x", {})
    assert result["timeout"] is True
    assert "Timeout" in result["response"]
    assert result["model"] == "model-x"


def test_run_calls_cancel_fn_with_worker_ident_on_timeout() -> None:
    supervisor = AgentSupervisor(timeout=1)
    calls: list[int] = []

    def cancel_fn(ident: int) -> None:
        calls.append(ident)

    supervisor.run(_SlowAgent(), "task", "model", {}, cancel_fn=cancel_fn)
    assert len(calls) == 1
    assert isinstance(calls[0], int)


def test_run_ignores_cancel_fn_exception() -> None:
    """Une exception dans cancel_fn ne doit jamais remonter à l'appelant."""
    supervisor = AgentSupervisor(timeout=1)

    def failing_cancel_fn(ident: int) -> None:
        raise RuntimeError("cancel a échoué")

    result = supervisor.run(_SlowAgent(), "task", "model", {}, cancel_fn=failing_cancel_fn)
    assert result["timeout"] is True


def test_init_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be > 0"):
        AgentSupervisor(timeout=0)


def test_init_uses_default_when_timeout_is_none() -> None:
    # Ne doit pas lever : retombe sur AGENT_TIMEOUT_SECONDS.
    supervisor = AgentSupervisor(timeout=None)
    assert supervisor._timeout > 0
