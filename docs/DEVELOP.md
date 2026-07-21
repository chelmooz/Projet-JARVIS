# Guide du développeur — JARVIS Portable Edition

Ce guide complète le `README.md` et le `CHANGELOG.md` pour contribuer au code.

## Prérequis

- Python 3.10+ (un Python portable 3.12 est fourni sur clef pré-remplie)
- Ollama portable (téléchargé automatiquement au 1er lancement)
- `pip install -r requirements.txt` (ou via `launchers/JARVIS.bat`)

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
| `config/` | Constantes, chemins, adaptateurs |
| `controllers/` | Routes FastAPI (`routes/`) + middleware (CSP, rate-limit) |
| `models/` | Dataclasses + schémas Pydantic |
| `ports/` | Interfaces abstraites (Protocol) |
| `services/` | Métier : inference, vector store, mémoire, launcher |
| `agents/` | Factory + profils des 5 agents |
| `graph/` | Orchestrateur séquentiel multi-agent |
| `memory/` | Stockage local JSON (runtime) |
| `static/` | Interface web HTML/CSS/JS |
| `tests/` | Suite pytest (TDD) |
| `scripts/` | Utilitaires (install, doctor) |
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

## Intégrité des binaires

`services/launcher.py` vérifie le SHA256 du binaire Ollama téléchargé contre les
`sha256sums.txt` officiels (avec repli offline : si la source est indisponible,
l'install ne bloque pas).
