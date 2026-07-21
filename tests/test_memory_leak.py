"""Test de fuite mémoire — exécute une boucle de requêtes et vérifie l'empreinte.

Mécanisme : on mesure le RSS avant et après ~100 requêtes GET sur un endpoint
léger (/api/status). Après gc.collect(), la croissance doit rester sous un
seuil tolérant (5 Mo) — sinon risque de fuite évidente.

Si aucun outil de mesure n'est disponible, le test est skip proprement.
"""

import gc

import pytest
from fastapi.testclient import TestClient

from controllers.router import app
from tests._mem import get_rss_bytes

# Seuil de tolérance : croissance max acceptable entre début et fin de boucle
RSS_GROWTH_TOLERANCE_BYTES = 5 * 1024 * 1024  # 5 Mo

_SKIP_REASON = ""
try:
    get_rss_bytes()
    _CAN_MEASURE = True
except RuntimeError as exc:
    _CAN_MEASURE = False
    _SKIP_REASON = str(exc)

pytestmark = pytest.mark.skipif(not _CAN_MEASURE, reason=_SKIP_REASON)

client = TestClient(app)


def test_memory_leak_status_endpoint():
    """La boucle de GET /api/status ne doit pas faire gonfler le RSS anormalement."""
    # Warm-up : échauffe le cache / imports pour ne pas polluer la baseline
    for _ in range(3):
        client.get("/api/status")
    gc.collect()

    rss_before = get_rss_bytes()

    # Boucle de requêtes légères
    for _ in range(100):
        resp = client.get("/api/status")
        assert resp.status_code == 200

    gc.collect()
    rss_after = get_rss_bytes()

    growth = rss_after - rss_before
    assert growth < RSS_GROWTH_TOLERANCE_BYTES, (
        f"Fuite mémoire suspecte : RSS +{growth / (1024 * 1024):.2f} Mo "
        f"sur 100 requêtes (tolérance {RSS_GROWTH_TOLERANCE_BYTES / (1024 * 1024):.0f} Mo)"
    )
