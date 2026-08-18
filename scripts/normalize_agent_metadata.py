#!/usr/bin/env python3
"""Script de normalisation des métadonnées agent dans l'index vectoriel.

Ajoute le préfixe @ aux valeurs d'agent qui n'en ont pas.
Ex: 'dev' -> '@dev', 'cyber' -> '@cyber', 'hardware' -> '@hardware'
"""

import json
import shutil
from pathlib import Path

VECTOR_INDEX_PATH = Path("memory/vector_index.json")
BACKUP_PATH = Path("memory/vector_index.json.bak")

VALID_AGENTS = {
    "dev": "@dev",
    "cyber": "@cyber",
    "hardware": "@hardware",
    "network": "@network",
    "vision": "@vision",
    "orchestrateur": "@orchestrateur",
    "lead": "@lead",
}


def normalize_agent(agent: str) -> str:
    """Normalise une valeur d'agent en ajoutant @ si nécessaire."""
    if not agent:
        return agent
    if agent.startswith("@"):
        return agent
    return VALID_AGENTS.get(agent, f"@{agent}")


def main() -> None:
    print(f"Chargement de {VECTOR_INDEX_PATH}...")
    with VECTOR_INDEX_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    documents = data.get("documents", [])
    print(f"Documents trouvés: {len(documents)}")

    changes = 0
    agents_before = set()
    agents_after = set()

    for doc in documents:
        metadata = doc.get("metadata", {})
        agent = metadata.get("agent")
        if agent:
            agents_before.add(agent)
            normalized = normalize_agent(agent)
            if normalized != agent:
                metadata["agent"] = normalized
                changes += 1
            agents_after.add(normalized)

    print(f"Modifications effectuées: {changes}")
    print(f"Agents avant: {sorted(agents_before)}")
    print(f"Agents après: {sorted(agents_after)}")

    if changes > 0:
        print(f"Sauvegarde de l'ancien fichier vers {BACKUP_PATH}...")
        shutil.copy2(VECTOR_INDEX_PATH, BACKUP_PATH)

        print("Écriture du fichier normalisé...")
        with VECTOR_INDEX_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print("Terminé.")
    else:
        print("Aucune modification nécessaire.")


if __name__ == "__main__":
    main()
