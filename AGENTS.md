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
| `@cyber` | `ornith-1.0-9b` | ~9,0 Go |
| `@dev` | `deepseek-coder-v2-lite-instruct` | ~4,0 Go |
| `@network` | `ornith-1.0-9b` | ~9,0 Go |
| `@hardware` | `qwen2.5:7b` | ~4,5 Go |
| `@vision` | `llama3.2-vision:11b-instruct-q4_K_M` | ~7,0 Go |

> `ornith-1.0-9b` équipe deux agents (@cyber et @network), d'où sa présence en double.
> `nomic-embed-text-v2-moe` (embeddings, ~0,6 Go) équipe la recherche vectorielle (RAG),
> pas un agent de chat.

> ⚠️ Ne pas confondre avec le champ `"model"` de `config/agent_profiles.json` : c'est le
> modèle **par défaut du profil** (persona/prompt), affiché dans l'onglet Agents avant
> toute réassignation. Le modèle **effectivement utilisé** en chat est celui ci-dessus,
> tant qu'aucune réassignation n'a été faite pour l'agent concerné.

Les modèles peuvent être changés via l'onglet **Agents** dans l'interface web ou l'API `/api/agents/assign`.
