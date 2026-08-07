"""TDD — aucun tag de modèle HF cassé ne doit subsister dans le code source suivi par git.

Bug réel (déploiement Windows du 07/08/2026, suite de W-DEPLOY-2) : le README avait
été corrigé (5 repos HF cassés remplacés), mais 21 fichiers du code source
(config/, services/, static/, tests/, docs) référençaient encore les anciens tags
cassés — restés invisibles car aucun test ne les vérifiait. `ollama pull` réussissait
avec les tags corrigés sur la clé USB, mais JARVIS (config/agent_profiles.json,
services/selector.py, config/constants.py DEFAULT_MODEL) aurait cherché les modèles
sous leurs anciens noms cassés auprès d'Ollama → 404 silencieux à l'exécution.
"""
import os
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BROKEN_TAGS = [
    "hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M",
    "hf.co/ibm-granite/granite-4.1-8b-instruct-GGUF:Q4_K_M",
    "hf.co/mradermacher/DeepHat-V1-7B-i1-GGUF:Q4_K_M",
    "hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-GGUF:Q4_K_M",
    "hf.co/bartowski/Llama-3.2-11B-Vision-Instruct-GGUF:Q4_K_M",
]

# Fichiers texte suivis par git, hors .git/ lui-même et hors les artefacts binaires
# (modèles, venv, node_modules) qui ne sont de toute façon jamais trackés.
TRACKED_TEXT_GLOBS = ("*.py", "*.json", "*.yaml", "*.yml", "*.js", "*.md")


def _tracked_files():
    result = subprocess.run(
        ["git", "ls-files"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    )
    # BACKLOG.md est un changelog : il documente volontairement les anciens tags
    # cassés comme trace historique (colonne "avant correction"), pas comme config
    # active — exclu du scan pour ne pas produire de faux positif.
    return [
        line for line in result.stdout.splitlines()
        if line.endswith((".py", ".json", ".yaml", ".yml", ".js", ".md"))
        and line != "BACKLOG.md"
    ]


def test_no_broken_model_tags_in_tracked_source():
    offenders = []
    for rel_path in _tracked_files():
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        try:
            with open(abs_path, encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for tag in BROKEN_TAGS:
            if tag in content:
                offenders.append((rel_path, tag))

    assert not offenders, (
        "Tags de modèles HF cassés encore référencés dans le code source suivi : "
        + ", ".join(f"{path} -> {tag}" for path, tag in offenders)
    )
