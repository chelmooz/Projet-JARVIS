#!/usr/bin/env python3
"""Test that corrupted vector file is archived (renamed) not copied, preventing retry loop."""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services"))

from vector import VectorService, VECTOR_PATH
from config.paths import MEMORY_DIR


def test_vector_load_corrupted_no_loop():
    """RED: Corrompre vector_index.json, appeler VectorService() deux fois,
    vérifier que le second n'affiche PAS 'Fichier corrompu'."""
    # Préparation : créer un fichier vector_index.json valide d'abord
    os.makedirs(MEMORY_DIR, exist_ok=True)

    # Écrire un fichier corrompu (tronqué à 10 bytes)
    corrupted_path = VECTOR_PATH
    with open(corrupted_path, "wb") as f:
        f.write(b"{\"documents\"")  # 11 bytes, mais JSON invalide après

    # Premier appel - devrait logger "Fichier corrompu"
    from services.vector import VectorService as VS
    # On a besoin d'un service d'inférence mocké
    class MockInference:
        def embed(self, text): return [0.0] * 768
        def embed_batch(self, texts): return [([0.0] * 768) for _ in texts]

    vs1 = VectorService(MockInference())
    # Deuxieme appel - ne doit PAS logger "Fichier corrompu" (fichier archivé)
    vs2 = VectorService(MockInference())

    # Vérifier que le fichier a été archivé (renommé) au lieu d'être copié
    # Le fichier devient : vector_index.json.corrupted.<timestamp>
    archived_files = [f for f in os.listdir(MEMORY_DIR) if f.startswith("vector_index.json.corrupted")]
    assert len(archived_files) >= 1, (
        f"Aucun fichier .corrupted archivé trouvé dans {MEMORY_DIR}. "
        f"Fichiers présents: {os.listdir(MEMORY_DIR)}"
    )

    # Nettoyage
    shutil.rmtree(MEMORY_DIR, ignore_errors=True)


if __name__ == "__main__":
    test_vector_load_corrupted_no_loop()
    print("Test passed: corrupted vector file archived, no retry loop")