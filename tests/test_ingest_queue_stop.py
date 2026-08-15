#!/usr/bin/env python3
"""Verrou de comportement pour ``IngestQueue.stop()`` (audit P9).

RED : ``stop()`` ne fait que ``self._stop.set()`` — pas de join, pas de log.
Le contrat attendu : l'arrêt est déterministe —
1. si le worker est en train de traiter un item, ``stop(timeout=...)`` attend sa
   fin (drain de l'item en vol) ;
2. si le worker est toujours actif après le timeout, un warning explicite est
   journalisé (avec le nombre d'items restants en file) — plus d'arrêt silencieux
   qui laisse le thread daemon s'éteindre sans trace.
"""

import time
import unittest
from typing import Any

from services.ingest_queue import IngestQueue


class SlowVector:
    """Fake vector store : ``ingest_message`` lent (simule un embedding Ollama)."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.calls = 0

    def ingest_message(self, *args: Any) -> None:
        self.calls += 1
        time.sleep(self.delay)


class TestIngestQueueStop(unittest.TestCase):
    """TEST: stop() draine l'item en vol ou journalise un warning sur timeout."""

    @staticmethod
    def _busy_queue(delay: float, timeout: float) -> tuple[IngestQueue, SlowVector]:
        """File démarrée, un item en cours de traitement (in-flight) au moment de stop()."""
        vector = SlowVector(delay)
        q = IngestQueue(vector)
        q.start()
        q.enqueue("conv1", "msg1", "user", "contenu à indexer", 1.0)
        time.sleep(0.3)  # laisse le worker récupérer l'item et entrer dans le sleep
        return q, vector

    def test_stop_waits_for_in_flight_item(self) -> None:
        """RED : stop(timeout) doit attendre la fin de l'item en vol (drain)."""
        q, vector = self._busy_queue(delay=0.5, timeout=5.0)

        q.stop(timeout=5.0)

        self.assertEqual(vector.calls, 1, "L'item en vol doit avoir été traité")
        self.assertFalse(q._worker.is_alive(), "Le worker doit avoir terminé après le join")
        self.assertTrue(q._q.empty(), "La file doit être vide après le drain")

    def test_stop_logs_warning_when_worker_still_busy(self) -> None:
        """RED : worker toujours actif après timeout → warning explicite."""
        q, _ = self._busy_queue(delay=2.0, timeout=0.2)

        with self.assertLogs("jarvis.ingest", level="WARNING") as cm:
            q.stop(timeout=0.2)

        self.assertTrue(
            any("encore actif" in message for message in cm.output),
            f"Aucun warning signalant un worker encore actif : {cm.output}",
        )
        q.stop(timeout=5.0)

    def test_stop_logs_warning_with_remaining_count(self) -> None:
        """RED : le warning mentionne le nombre d'items restants en file."""
        vector = SlowVector(delay=2.0)
        q = IngestQueue(vector)
        q.start()
        q.enqueue("conv1", "msg1", "user", "premier", 1.0)
        q.enqueue("conv2", "msg2", "user", "second", 2.0)
        time.sleep(0.3)  # worker occupé sur msg1, msg2 reste en file

        with self.assertLogs("jarvis.ingest", level="WARNING") as cm:
            q.stop(timeout=0.2)

        self.assertTrue(
            any("1 message" in message for message in cm.output),
            f"Le warning doit compter l'item restant : {cm.output}",
        )
        q.stop(timeout=5.0)


if __name__ == "__main__":
    unittest.main()
