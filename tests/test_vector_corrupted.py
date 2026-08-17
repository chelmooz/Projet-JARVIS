#!/usr/bin/env python3
"""Test que fichier vector corrompu est archivé (renommé) non copié — pas de boucle de retry.

Version isolée (MT-KB-L2j GREEN) : n'écrit JAMAIS sur le vrai ``MEMORY_DIR``.
``VECTOR_PATH`` est monkeypatché vers ``tmp_path/vector_index.json`` — pattern
éprouvé dans ``tests/test_vector_corrupted_isolated.py`` et
``tests/test_vector_service_characterization.py``.

Historique : le test historique écrivait sur le VRAI ``MEMORY_DIR`` (via
``os.makedirs`` + écriture sur ``VECTOR_PATH`` non patché) puis le détruisait à
chaque exécution via ``shutil.rmtree`` ciblant ``MEMORY_DIR`` (``ignore_errors=True``)
— ce qui effaçait l'index vectoriel Phase 2 (904 docs) à chaque lancement de pytest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.vector import VectorService


class _StubInference:
    """Service d'inférence factice : embeddings constants 768-dim.

    Référence les méthodes appelées par ``VectorService`` (``embed`` warmup,
    ``embed_batch`` vectorisation) sans dépendance Ollama.
    """

    def embed(self, text: str) -> list[float]:
        return [0.0] * 768

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 768 for _ in texts]


def test_vector_load_corrupted_no_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Index corrompu : 1er appel archive, 2e appel ne relogge pas « Fichier corrompu ».

    Vérifie (intention préservée du test historique) :
      - Le fichier corrompu est renommé en ``vector_index.json.corrupted.<ts>``
        (pas de copie = pas de boucle de retry).
      - Le 2e appel ne déclenche PAS un nouvel archivage (``vector_index.json``
        déjà renommé, plus de fichier à corrompre) → exactement 1 archive.
      - L'index reste vide après archivage (``stats()["total"] == 0``).

    Tout est isolé sur ``tmp_path`` : aucun accès au vrai ``MEMORY_DIR``.
    """
    vpath = tmp_path / "vector_index.json"
    monkeypatch.setattr("services.vector.VECTOR_PATH", str(vpath))

    # Écrire un fichier corrompu (JSON invalide : tronqué après 11 octets)
    vpath.write_bytes(b'{"documents"')

    # Premier appel : archive le fichier corrompu (renommage en .corrupted.<ts>)
    VectorService(_StubInference())
    # Deuxième appel : ne doit PAS relogger « Fichier corrompu » (fichier déjà renommé)
    svc = VectorService(_StubInference())

    # Exactement 1 archive (pas de boucle) — le 2e appel n'a rien archivé
    archived = [p.name for p in tmp_path.iterdir() if p.name.startswith("vector_index.json.corrupted")]
    assert len(archived) == 1, f"Exactement 1 fichier .corrupted.<ts> attendu dans {tmp_path}, trouvé : {archived}"

    # Index vide après archivage
    assert svc.stats()["total"] == 0


if __name__ == "__main__":
    import sys

    sys.exit("Run via 'pytest tests/test_vector_corrupted.py' — fixtures tmp_path/monkeypatch required.")
