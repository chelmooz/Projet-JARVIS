"""Lot 5.2 — API publique du setup des middlewares (TDD).

Vérifie que ``setup_middlewares`` est un symbole public (plus de préfixe
``_``) et que ``context.py`` l'importe sous ce nom (sinon l'import échoue).
"""

from __future__ import annotations

import pytest

from controllers import context as context_module
from controllers.middlewares import setup_middlewares


def test_setup_middlewares_is_public_callable() -> None:
    assert callable(setup_middlewares)


def test_build_app_calls_setup_middlewares(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    def _fake_setup(app: object) -> None:
        called.append("setup_middlewares")

    monkeypatch.setattr(context_module, "setup_middlewares", _fake_setup)
    context_module.build_app()
    assert called == ["setup_middlewares"]
