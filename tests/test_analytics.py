#!/usr/bin/env python3
"""Test that analytics stats work correctly.

Version isolée (MT-KB-L2m) : ``ANALYTICS_PATH`` redirigée vers ``tmp_path`` pour
chaque test — aucun accès au vrai ``memory/analytics.json`` de production. Pattern
identique à MT-KB-L2j sur ``tests/test_vector_corrupted.py`` (cohérence d'isolation).

Historique : les 2 tests historiques lisaient ``memory/analytics.json`` de production
→ ``test_analytics_no_queries`` échouait dès que le dashboard JARVIS était utilisé
(queries accumulées dans ``analytics.json``) ; ``test_analytics_stats_basic`` passait
par hasard car il ne vérifie que la présence de clés, mais restait couplé au disque
de production — couplage latent dès que la structure de sortie changerait.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

import services.analytics as analytics_module
from services.analytics import AnalyticsService

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _isolated_analytics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AnalyticsService:
    """Fixture helper : ``AnalyticsService`` avec ``ANALYTICS_PATH`` isolé sur ``tmp_path``.

    Écrit un ``analytics.json`` vide (``{}``) — ``_load()`` → ``_migrate()`` produit
    ``{"queries": [], "agents": {}, "models": {}}`` (cf. ``services/analytics.py:55-62``).
    Aucun accès au vrai ``MEMORY_DIR/analytics.json`` de production.
    """
    fake_path = tmp_path / "analytics.json"
    fake_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(analytics_module, "ANALYTICS_PATH", str(fake_path))
    return AnalyticsService()


def test_analytics_stats_basic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GREEN : structure de stats correcte (sans ``total_conversations``) — version isolée."""
    analytics = _isolated_analytics(tmp_path, monkeypatch)
    stats = analytics.get_stats()
    # Vérifier que la structure est correcte (total_conversations retiré)
    assert "total_queries" in stats
    assert "success_rate" in stats
    assert "avg_latency_ms" in stats
    assert "agents" in stats
    assert "models" in stats
    assert "total_conversations" not in stats


def test_analytics_no_queries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GREEN : sans requêtes, les stats sont vides/zeros — version isolée."""
    analytics = _isolated_analytics(tmp_path, monkeypatch)
    stats = analytics.get_stats()
    assert stats["total_queries"] == 0
    assert stats["success_rate"] == 0.0
    assert stats["avg_latency_ms"] == 0.0
    assert stats["agents"] == {}
    assert stats["models"] == {}


if __name__ == "__main__":
    sys.exit("Run via 'pytest tests/test_analytics.py' — fixtures tmp_path/monkeypatch required.")
