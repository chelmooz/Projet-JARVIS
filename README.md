# JARVIS Portable Edition — v6.0

Assistant IA **100 % local, portable et hors-ligne** : 5 agents spécialisés, analyse
d'images (OCR + LLM), mémoire vectorielle locale, et une interface web autonome.
Aucun cloud, aucune dépendance SaaS, aucune donnée envoyée à l'extérieur.

- **Backend** : FastAPI (`jarvis.py`) sur `http://localhost:8000`
- **Moteur LLM** : Ollama portable sur `127.0.0.1:11436`
- **Frontend** : HTML/CSS/JS vanilla (modules ES), `static/`
- **Cible** : clé USB / poste mono-utilisateur, Windows, Linux, macOS

---

## Sommaire

1. [Contenu du projet](#1-contenu-du-projet)
2. [Déploiement & installation](#2-déploiement--installation)
3. [Mode d'emploi (utilisateur)](#3-mode-demploi-utilisateur)
4. [Architecture](#4-architecture)
5. [Tests & développement](#5-tests--développement)
6. [Documentation & ADR](#6-documentation--adr)

---

## 1. Contenu du projet

| Élément | Rôle |
|---------|------|
| `jarvis.py` | Point d'entrée unique (pre-flight, démarrage Ollama + Uvicorn) |
| `controllers/` | Routes FastAPI (`routes/`) + middleware (CSP, rate-limit), composition root |
| `models/` | Dataclasses + schémas Pydantic (DTO d'entrée) |
| `ports/` | Interfaces abstraites (Protocol) — découplage métier/infra |
| `services/` | Métier : inference, vector store, mémoire, RAG, pipeline, launcher, sanitize, skills |
| `services/adapters/` | Adaptateur Ollama (backend LLM) |
| `services/diagnostic_ext/`, `services/diagnostics/` | Diagnostics matériels (CPU/RAM/GPU/disque) |
| `agents/` | Factory + profils des **5 agents** spécialisés |
| `graph/` | Orchestrateur séquentiel multi-agent (`AgentGraph`) |
| `memory/` | Stockage local JSON (conversations, habits, analytics, vector_index) |
| `config/` | Constantes, chemins, profils agents, routage, pipelines |
| `static/` | Interface web (HTML/CSS/JS modules) |
| `launchers/` | `JARVIS.bat` (Windows) / `JARVIS.sh` (Linux/macOS) — lanceurs portables |
| `scripts/` | Utilitaires (install, doctor, backup, restore) |
| `bin/` | Binaires portables (Ollama, outils diagnostic) |
| `docs/` | Architecture, RUNBOOK, guide dev, ADR |
| `tests/` | Suite pytest (Python, TDD) |
| `static/test/` | Tests frontend (vitest/jsdom) |

### Les 5 agents

| @préfixe | Agent | Domaine |
|----------|-------|---------|
| `@cyber` | Data / Secu / Docs | Sécurité, logs, audit |
| `@dev` | Tech Lead Full-Stack | Scripting & développement |
| `@network` | Dev Local & Ops | Réseaux & connectivité |
| `@hardware` | Orchestrateur | Matériel & diagnostics |
| `@vision` | Designer UX + OCR | Analyse d'images (texte extrait via RapidOCR, puis analysé par LLM) |

Alias : `@orchestrateur`/`@techlead`/`@devops` → dev, `@datasecu` → cyber.
Le routage complet est dans `config/agent_routing.yaml`.

---

## 2. Déploiement & installation

**Aucune installation système requise** : le projet est 100 % portable sur clé USB.

### Lancement (méthode recommandée)

```bash
# Windows : double-clic sur
launchers/JARVIS.bat

# Linux / macOS :
./launchers/JARVIS.sh
```

Le lanceur démarre Ollama (port 11436) puis l'API JARVIS (port 8000) et ouvre
l'interface. Ollama et ses modèles sont téléchargés/importés automatiquement au
premier lancement (Python portable 3.12 fourni sur la clé).

### Lancement manuel

```bash
python jarvis.py        # Windows
python3 jarvis.py       # Linux / macOS
# → Interface : http://localhost:8000
# → API docs  : http://localhost:8000/docs
# → Mode dev (logs verbeux) : JARVIS_DEV=1 python jarvis.py
```

### Prérequis (hors clé pré-remplie)

- Python 3.10+ (un Python portable 3.12 est fourni)
- Ollama portable (téléchargé automatiquement au 1er lancement)
- `cp .env.example .env` puis `pip install -r requirements.txt` si démarrage hors lanceur

### Changer le port

```bash
PORT=8001 python3 jarvis.py                      # Linux / macOS
$env:PORT=8001; python jarvis.py                 # Windows (PowerShell)
set PORT=8001 && python jarvis.py                # Windows (cmd)
```

### Vérification des services

```bash
curl http://localhost:8000/api/status            # état JARVIS
curl http://localhost:11436/api/tags             # modèles Ollama
python jarvis.py --diag                          # diagnostic complet (couleurs OK/WARN/FAIL)
```

> Déploiement CI / Docker (Ollama) et tests d'intégration : voir `docs/RUNBOOK.md`.

---

## 3. Mode d'emploi (utilisateur)

Ouvrez `http://localhost:8000`. L'interface est organisée en **9 onglets** SPA :

1. **Chat** — conversation libre avec l'agent en cours.
2. **Conversations** — historique des sessions.
3. **Agents** — profils des 5 agents et modèle assigné (modifiable à chaud).
4. **Skills** — compétences activables/désactivables.
5. **Vision** — déposez une image → extraction de texte (RapidOCR) + analyse LLM.
6. **Outils** — diagnostics matériels.
7. **Analytics** — statistiques d'usage.
8. **Réglages** — modèle par défaut, backend, mode hors-ligne, dossiers autorisés.
9. **Console** — voir ci-dessous.

### Commandes `@agent`

Tapez une commande ciblée vers un agent :

```
@cyber scan le firewall
@dev écris un script PowerShell de sauvegarde
@vision décris cette capture
```

Envoyée via le Chat ou la **Console**, la commande est routée vers l'agent
correspondant (`config/agent_routing.yaml`).

### Console (9ᵉ onglet)

Onglet dédié aux commandes `@agent tâche` :

- Saisie directe, **scrollback** append-only avec badge agent par ligne.
- **Historique** des commandes (flèches ↑/↓, persistant `localStorage`, 50 max ;
  les réponses ne sont jamais persistées).
- **Indicateur de connexion** (vert = Ollama joignable).

### Command Palette (Ctrl/⌘+K)

Disponible **partout** dans l'interface :

- `Ctrl`+`K` (ou `⌘`+`K`) ouvre l'overlay.
- Saisissez `@` → autocomplétion des agents (préfixes de `agent_routing.yaml`).
- `Entrée` exécute la commande inline (`source: palette`).
- `Échap` ferme.
- Bouton **« Ouvrir en Console »** → bascule vers l'onglet Console avec la
  commande pré-remplie (handoff Palette → Console).

### Analyse d'image (Vision)

Dans l'onglet Vision, déposez/collez une image. Le texte est extrait par
**RapidOCR** (moteur ONNX déterministe, sans modèle Ollama multimodal), puis
analysé par le LLM texte `Qwen2.5-7B`. Si l'analyse LLM échoue, le texte OCR
brut est retourné (dégradation gracieuse).

---

## 4. Architecture

Architecture hexagonale (ports & adapters) — voir `docs/architecture.md` pour le
schéma Mermaid détaillé.

```text
UI (static/) ──HTTP/FastAPI──▶ controllers/ ──▶ ports/ ──▶ agents/ · services/ · graph/
                                                                     │
                                                              services/adapters/
                                                                     │
                                                            Ollama portable (11436)
```

- **Stockage** : JSON local dans `memory/` (conversations, habits, analytics, vector_index).
- **Démarrage** : `jarvis.py` → `ProcessManager` (Ollama + JARVIS Core).
- **Flux** : `POST /api/jarvis` → `graph/AgentGraph` → `selector.py` (modèle) →
  `services/inference.py` → adaptateur Ollama → réponse persistée.

---

## 5. Tests & développement

```bash
# Python (TDD, pytest)
python -m pytest -v
ruff check .                 # lint (config stricte dans pyproject.toml)
ruff check --fix .           # correction auto

# Frontend (vitest/jsdom)
cd static && npm install && npx vitest run

# Diagnostic
python scripts/jarvis_doctor.py
```

Conventions : TDD (rouge → vert → refactor), Clean Code / KISS, single source of
truth des versions dans `config/constants.py`. Voir `docs/DEVELOP.md` pour
contribuer (ajouter un agent, un skill, profil low I/O/VRAM).

---

## 6. Documentation & ADR

- `docs/architecture.md` — schéma et flux.
- `docs/RUNBOOK.md` — runbook complet (services, diagnostics, CI, sauvegarde).
- `docs/DEVELOP.md` — guide développeur.
- `CHANGELOG.md` — historique des versions (dont la v6.0 : Console + Palette Ctrl+K, Vision OCR).
- `docs/adr/` — Architectural Decision Records (ADR-001 à ADR-010) :
  MVC/ports, sandbox CPU-only, pipeline RAG, fail-fast embedding, Vision OCR+LLM…

---

*JARVIS Portable Edition v6.0 — 100% local, zéro installation système, zéro cloud.*
