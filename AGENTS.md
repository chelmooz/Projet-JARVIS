# Agents JARVIS

## Routage (préfixes `@`)

| @mention | Agent | Module | Profil interne | Prompt domaine |
|----------|-------|--------|----------------|----------------|
| `@cyber` | CyberAgent | `agents/cyber.py` | datasecu | Sécurité, logs, audit |
| `@dev` | GenericAgent | `agents/generic.py` | techlead | Scripting & développement |
| `@network` | GenericAgent | `agents/generic.py` | devops | Réseaux & connectivité |
| `@hardware` | GenericAgent | `agents/generic.py` | orchestrateur | Matériel & diagnostics |
| `@vision` | VisionAgent | `agents/vision.py` | designer | Analyse d'images |

## Backend

- Ollama portable sur `127.0.0.1:11436`
- API JARVIS sur `127.0.0.1:8000`

## Modèles utilisés par agent

Résolution réelle du modèle par `services/selector.py` (`fallback_models()`), sauf
réassignation explicite via l'onglet **Agents** de l'interface web ou l'API
`/api/agents/assign` (persistée dans `config/model_preferences.json`) :

| @mention | Modèle | Taille |
|----------|--------|--------|
| `@cyber` | `hf.co/mradermacher/DeepHat-V1-7B-i1-GGUF:Q4_K_M` | ~4,7 Go |
| `@dev` | `hf.co/ibm-granite/granite-4.1-8b-instruct-GGUF:Q4_K_M` | ~4,9 Go |
| `@network` | `hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-GGUF:Q4_K_M` | ~4,9 Go |
| `@hardware` | `hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M` | ~4,7 Go |
| `@vision` | `hf.co/bartowski/Llama-3.2-11B-Vision-Instruct-GGUF:Q4_K_M` | ~7,0 Go |

> `hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M` (embeddings, ~0,6 Go) équipe la recherche vectorielle (RAG),
> pas un agent de chat.

> ⚠️ Ne pas confondre avec le champ `"model"` de `config/agent_profiles.json` : c'est le
> modèle **par défaut du profil** (persona/prompt), affiché dans l'onglet Agents avant
> toute réassignation. Le modèle **effectivement utilisé** en chat est celui ci-dessus,
> tant qu'aucune réassignation n'a été faite pour l'agent concerné.

Les modèles peuvent être changés via l'onglet **Agents** dans l'interface web ou l'API `/api/agents/assign`.
