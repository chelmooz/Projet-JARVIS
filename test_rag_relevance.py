"""MT-KB-L5a-test — Évaluation pertinence RAG (lecture seule).

Interroge VectorService sur l'index réel (copie temporaire, aucune mutation du
fichier memory/vector_index.json). Embeddings de requête via Ollama réel.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import orjson

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

import services.vector as svc_mod
from services.inference import InferenceService
from services.vector import VectorService

REAL_INDEX = ROOT / "memory" / "vector_index.json"

# 12 questions (agent filter tel que demandé par la MT)
QUESTIONS = [
    ("@dev",     "Comment fonctionne pkg_resources dans setuptools ?"),
    ("@dev",     "Comment déclarer des entry_points dans un projet Python ?"),
    ("@dev",     "Quelles alternatives modernes à pkg_resources pour gérer les ressources ?"),
    ("@hardware", "Comment utiliser taskset pour contrôler l'affinité CPU d'un processus ?"),
    ("@hardware", "Quelles commandes PowerShell pour surveiller la mémoire système ?"),
    ("@hardware", "Comment diagnostiquer un problème réseau avec PowerShell ?"),
    ("@designer", "Comment structurer un fichier pyproject.toml pour un projet portable ?"),
    ("@designer", "Quelles conventions de nommage pour les packages Python ?"),
    ("@designer", "Comment documenter les dépendances d'un projet Python ?"),
    ("@cyber",    "Quels risques de sécurité liés à pkg_resources ?"),
    ("@cyber",    "Comment vérifier les permissions d'un fichier sous Linux avec chmod ou ls -la ?"),
    ("@cyber",    "Comment sécuriser les dépendances d'un projet Python local ?"),
]


def main() -> int:
    if not REAL_INDEX.exists():
        print("ERREUR: index introuvable", REAL_INDEX)
        return 2

    # Copie temporaire -> garantie lecture seule sur le vrai fichier
    tmp = Path(tempfile.mkdtemp()) / "vector_index.copy.json"
    shutil.copyfile(REAL_INDEX, tmp)
    svc_mod.VECTOR_PATH = str(tmp)

    inference = InferenceService()
    if not inference.is_healthy():
        print("ERREUR: Ollama indisponible (11436) -> impossible d'embedder les requêtes")
        return 2

    vs = VectorService(inference_service=inference)

    # Distribution agent dans l'index réel
    agents = Counter(d.get("metadata", {}).get("agent") for d in vs._data["documents"])
    sources = Counter(d.get("metadata", {}).get("source") for d in vs._data["documents"])
    print("=== INDEX RÉEL (copie) ===")
    print("TOTAL docs:", len(vs._data["documents"]))
    print("AGENT distribution:", dict(agents))
    print("SOURCE distribution:", dict(sources))
    print()

    print("=== RÉSULTATS BRUTS RETRIEVAL ===")
    for i, (agent_filter, q) in enumerate(QUESTIONS, 1):
        t0 = time.time()
        try:
            filtered = vs.search(q, top_k=5, agent=agent_filter, sim_threshold=0.5)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}] AGENT={agent_filter} | ERR filtered: {e!r}")
            filtered = []
        try:
            unfiltered = vs.search(q, top_k=5, agent=None, sim_threshold=0.5)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}] AGENT={agent_filter} | ERR unfiltered: {e!r}")
            unfiltered = []
        dt = time.time() - t0

        f_top = filtered[0]["score"] if filtered else 0.0
        u_top = unfiltered[0]["score"] if unfiltered else 0.0
        f_src = filtered[0]["metadata"].get("source") if filtered else "-"
        f_agent = filtered[0]["metadata"].get("agent") if filtered else "-"
        u_src = unfiltered[0]["metadata"].get("source") if unfiltered else "-"
        u_agent = unfiltered[0]["metadata"].get("agent") if unfiltered else "-"
        f_snip = (filtered[0]["text"][:160].replace("\n", " ") if filtered else "-")
        u_snip = (unfiltered[0]["text"][:160].replace("\n", " ") if unfiltered else "-")

        print(f"[{i}] AGENT_FILTER={agent_filter} ({dt:.1f}s)")
        print(f"    FILTERED : chunks={len(filtered)} top_score={f_top:.4f} "
              f"src={f_src} agent={f_agent}")
        print(f"      -> {f_snip}")
        print(f"    UNFILTERED: chunks={len(unfiltered)} top_score={u_top:.4f} "
              f"src={u_src} agent={u_agent}")
        print(f"      -> {u_snip}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
