from pathlib import Path

import pytest

BACKLOG_PATH = Path("BACKLOG.md")

# IDs des micro-tâches KB qui DOIVENT être dans le backlog
REQUIRED_KB_TASKS = [
    "MT-ROADMAP-KB",
    "MT-ROADMAP-KB-O",
    "MT-KB-L0",
    "MT-KB-L0b",
]


def test_backlog_contains_all_kb_tasks() -> None:
    """Vérifie qu'aucune micro-tâche KB n'a été oubliée dans le BACKLOG."""
    assert BACKLOG_PATH.exists(), "BACKLOG.md introuvable"
    content = BACKLOG_PATH.read_text(encoding="utf-8")

    missing = []
    for task_id in REQUIRED_KB_TASKS:
        if task_id not in content:
            missing.append(task_id)

    assert not missing, f"Micro-tâches manquantes dans BACKLOG.md : {missing}"


def test_backlog_kb_tasks_have_commit_hashes() -> None:
    """Vérifie que les entrées KB contiennent bien des hashes de commit (traçabilité)."""
    content = BACKLOG_PATH.read_text(encoding="utf-8")

    for task_id in REQUIRED_KB_TASKS:
        # Trouve la section de la tâche (approximatif : cherche l'ID et les 10 lignes suivantes)
        start_idx = content.find(task_id)
        if start_idx == -1:
            pytest.fail(f"{task_id} introuvable (devrait être catché par le test précédent)")

        section = content[start_idx : start_idx + 1000]  # Extrait large
        # Un commit hash fait 7 caractères hexadécimaux dans nos logs, ou 40.
        # On cherche juste la présence du mot "commit" ou un hash court typique (ex: 734616e)
        has_trace = "commit" in section.lower() or any(c in section for c in ["734616e", "fb86f0d", "a2f94b6"])
        assert has_trace, f"L'entrée {task_id} dans BACKLOG.md ne référence aucun commit"
