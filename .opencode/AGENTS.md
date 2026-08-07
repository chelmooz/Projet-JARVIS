# Directive exécution — JARVIS Portable (Pré-déploiement)

- Micro-tâches uniquement — une seule action à la fois, pas de boucles
- `H:\Projet-JARVIS\BACKLOG.md` est mis à jour après chaque micro-tâche terminée
- Relire `BACKLOG.md` avant chaque nouvelle étape pour savoir où j'en suis
- Si une micro-tâche échoue, je la signale et je passe à la suivante (pas de retry infini)
- **Contexte pré-déploiement** : aucune machine installée, pas de serveur local ni test réseau possible

---

## Agents JARVIS — Routage (préfixes `@`)

| @mention | Agent | Module | Profil interne | Prompt domaine |
|----------|-------|--------|----------------|----------------|
| `@cyber` | CyberAgent | `agents/cyber.py` | datasecu | Sécurité, logs, audit |
| `@dev` | GenericAgent | `agents/generic.py` | techlead | Scripting & développement |
| `@network` | GenericAgent | `agents/generic.py` | devops | Réseaux & connectivité |
| `@hardware` | GenericAgent | `agents/generic.py` | orchestrateur | Matériel & diagnostics |
| `@vision` | VisionAgent | `agents/vision.py` | designer | Analyse d'images |

> **Note pré-déploiement** : Les agents sont optionnels. `@dev`, `@hardware`, `@network` sont les plus pertinents pour les scripts d'infrastructure (création LXC, Docker, réseau).

---

## Backend Local

- Ollama portable sur `127.0.0.1:11436`
- API JARVIS sur `127.0.0.1:8000`

---

## Modèles utilisés par agent

Résolution réelle du modèle par `services/selector.py` (`fallback_models()`), sauf
réassignation explicite via l'onglet **Agents** de l'interface web ou l'API
`/api/agents/assign` (persistée dans `config/model_preferences.json`) :

| @mention | Modèle | Taille |
|----------|--------|--------|
| `@cyber` | `hf.co/GGUF-A-Lot/DeepHat-V1-7B-GGUF:Q4_K_M` | ~4,7 Go |
| `@dev` | `hf.co/bartowski/ibm-granite_granite-4.1-8b-GGUF:Q4_K_M` | ~4,9 Go |
| `@network` | `hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF:Q8_0` | ~4,9 Go |
| `@hardware` | `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M` | ~4,7 Go |
| `@vision` | `hf.co/leafspark/Llama-3.2-11B-Vision-Instruct-GGUF:Q4_K_M` | ~7,0 Go |

> `hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M` (embeddings, ~0,6 Go) équipe la recherche vectorielle (RAG), pas un agent de chat.

> ⚠️ Ne pas confondre avec le champ `"model"` de `config/agent_profiles.json` : c'est le modèle **par défaut du profil** (persona/prompt), affiché dans l'onglet Agents avant toute réassignation. Le modèle **effectivement utilisé** en chat est celui ci-dessus, tant qu'aucune réassignation n'a été faite pour l'agent concerné.

Les modèles peuvent être changés via l'onglet **Agents** dans l'interface web ou l'API `/api/agents/assign`.

---

## Règles code projet

- Ruff (line length 120), pytest (`tests/`), types stricts
- Architecture MVC + Ports (composition root dans `jarvis.py` + `controllers/router.py`)
- 5 agents spécialisés, pas de cloud, tout local
- GitHub : repo local uniquement (pas de push auto)

---

## Key paths

- `H:\Projet-JARVIS\` : racine du repo
- `jarvis.py` : point d'entrée unique (pre-flight, Ollama, Uvicorn)
- `controllers/router.py` : Composition Root FastAPI + montage sous-routeurs
- `services/selector.py` : résolution modèles (`fallback_models()`, `select_model()`)
- `config/agent_routing.yaml` : mapping préfixes @ + mots-clés + fallback
- `config/model_preferences.json` : réassignations utilisateur persistées
- `BACKLOG.md` : journal des décisions + traces de session