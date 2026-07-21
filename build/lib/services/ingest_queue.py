"""File d'ingestion vectorielle asynchrone — auto-ingest des messages.

Responsabilité unique (SRP) : decoupler l'ajout d'un message (synchrone, sur le
chemin de requete) du calcul d'embedding (potentiellement lent, Ollama local).

Le worker est un thread daemon demarre explicitement via start() — uniquement
par le cycle de vie FastAPI (lifespan), pas par initialize(). Ainsi, les tests
qui appellent initialize() n'activent jamais l'embedding et ne polluent pas
l'index vectoriel.
"""
import logging
import queue
import threading

_logger = logging.getLogger("jarvis.ingest")


class IngestQueue:
    """File d'attente d'embeddings pour l'auto-ingest des conversations."""

    def __init__(self, vector, enabled: bool = True):
        self._vector = vector
        self._enabled = enabled
        self._q: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._worker = None

    def enqueue(self, conv_id: str, msg_id: str, role: str, content: str, ts):
        """Empile un message a indexer (non bloquant)."""
        if not self._enabled:
            return
        if not content or not content.strip():
            return
        self._q.put((conv_id, msg_id, role, content, ts))

    def start(self):
        """Demarre le worker daemon (idempotent)."""
        if self._worker and self._worker.is_alive():
            return
        if not self._enabled:
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        _logger.info("File d'ingestion vectorielle demarree")

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=1)
            except queue.Empty:
                continue
            try:
                conv_id, msg_id, role, content, ts = item
                self._vector.ingest_message(conv_id, msg_id, role, content, ts)
            except Exception as e:
                _logger.warning("Ingestion message echouee (conv=%s msg=%s): %s", conv_id, msg_id, e)
            finally:
                self._q.task_done()
