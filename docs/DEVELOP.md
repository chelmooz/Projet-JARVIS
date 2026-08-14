# Guide du développeur — JARVIS Portable Edition

Ce guide complète le `README.md` et le `CHANGELOG.md` pour contribuer au code.

## Prérequis

- Python 3.10+ (un Python portable 3.12 est fourni sur clef pré-remplie)
- Ollama portable (téléchargé automatiquement au 1er lancement)
- `cp .env.example .env && pip install .` (ou via `launchers/JARVIS.bat`)

Les dépendances sont épinglées dans `uv.lock` et `requirements.lock` (voir
section « Reproductibilité ») : `pip install -r requirements.txt` est obsolète.

## Lancer en local

```bash
# Dépendances
pip install -r requirements.txt
cp .env.example .env

# Démarrer (Ollama + JARVIS sur http://localhost:8000)
python jarvis.py
# ou en mode dev (logs verbeux)
JARVIS_DEV=1 python jarvis.py
```

## Diagnostic

```bash
python scripts/jarvis_doctor.py   # vérifie Python, .env, Ollama, port 11436
```

## Structure (couches ports & adapters)

| Dossier | Rôle |
|---------|------|
| `config/` | Constantes, chemins, profiles agents, pipelines |
| `controllers/` | Routes FastAPI (`routes/`) + middleware (CSP, rate-limit) |
| `models/` | Dataclasses + schémas Pydantic |
| `ports/` | Interfaces abstraites (Protocol) |
| `services/` | Métier : inference, vector store, mémoire, pipeline RAG, trace sidecar, score composite, chunker, launcher |
| `services/adapters/` | Adaptateur Ollama |
| `services/diagnostic_ext/` | Diagnostic étendu (exécution binaires externes) |
| `services/diagnostics/` | Diagnostics matériels (CPU, RAM, GPU, disque) |
| `agents/` | Factory + profils des 5 agents |
| `graph/` | Orchestrateur séquentiel multi-agent |
| `memory/` | Stockage local JSON (runtime) |
| `static/` | Interface web HTML/CSS/JS |
| `tests/` | Suite pytest (TDD) |
| `scripts/` | Utilitaires (install, doctor, backup, restore) |
| `docs/adr/` | Architectural Decision Records |

## Conventions

- **TDD** : rouge → vert → refactor pour toute modification.
- **Clean code / KISS** : pas de sur-ingénierie, pas de fichiers fantômes.
- **Lint** : `ruff check .` doit passer (config stricte dans `pyproject.toml`).
- **Single source of truth** : versions/`constants` dans `config/constants.py`.

## Ajouter un agent

1. Ajouter le profil dans `config/agent_profiles.json`.
2. Enregistrer le mapping modèle dans `agents/`.
3. Tester via `tests/test_agents.py`.

## Ajouter un skill

1. Créer `skills/<nom>/SKILL.md` (ou une entrée dans `config/skills.yaml`).
2. Vérifier l'injection dans `services/skills.py`.
3. Tester via `tests/test_skills.py`.

## Profil low I/O / low VRAM

Sur clef USB lente ou peu de RAM, activer :

```bash
export JARVIS_LOW_IO=1
```

Réduit la taille du cache vectoriel et le top-k de recherche.

## Reproductibilité (install offline)

Les dépendances Python sont épinglées une seule fois pour toutes :

- `uv.lock` — vérité source, versionné (généré par `uv lock`).
- `requirements.lock` — export plat de `uv.lock` pour pip, versionné
  (régénéré par `uv export --format requirements-txt --no-hashes --no-emit-project`).

Modifier une dépendance : `uv add <pkg>` puis régénérer les deux fichiers.

Installer **offline** sur une machine isolée :

```bash
# 1. Sur une machine connectée, préparer le dossier de wheels (~500 Mo)
python scripts/vendor_wheels.py

# 2. Sur la clé/la machine cible (dossier vendor_wheels/ présent à la racine)
python scripts/install.py        # détecte vendor_wheels/ → --no-index --find-links
```

Sans dossier `vendor_wheels/`, `scripts/install.py` retombe sur une install
pip en ligne. Détails : `docs/adr/ADR-012-distribution-offline.md`.

## Intégrité des binaires

`services/launcher.py` vérifie le SHA256 du binaire Ollama téléchargé contre les
`sha256sums.txt` officiels (avec repli offline : si la source est indisponible,
l'install ne bloque pas).
