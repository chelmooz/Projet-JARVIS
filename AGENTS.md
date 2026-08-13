# Agents JARVIS

## Routage (préfixes `@`)

| @mention | Agent | Module | Profil interne | Prompt domaine |
|----------|-------|--------|----------------|----------------|
| `@cyber` | CyberAgent | `agents/cyber.py` | datasecu | Sécurité, logs, audit |
| `@dev` | GenericAgent | `agents/generic.py` | techlead | Scripting & développement |
| `@network` | GenericAgent | `agents/generic.py` | devops | Réseaux & connectivité |
| `@hardware` | GenericAgent | `agents/generic.py` | orchestrateur | Matériel & diagnostics |
| `@vision` | VisionAgent | `agents/vision.py` → OCR via `services/ocr.py` (RapidOCR) | designer *(texte uniquement ; ignoré si image)* | Extraction de texte depuis une image (OCR) |

## Backend

- Ollama portable sur `127.0.0.1:11436`
- API JARVIS sur `127.0.0.1:8000`

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

> 👁️ **`@vision`** n'a pas de ligne ci-dessus : quand une image est présente, il n'appelle
> **aucun modèle Ollama**. `services/selector.py::select_vision_model()` renvoie la
> sentinelle `"rapidocr"` (télémétrie uniquement) et `agents/vision.py` délègue à
> **RapidOCR** (`services/ocr.py`, moteur ONNX déterministe, package `pip` pur).
> Sans image (texte seul), `@vision` retombe sur le profil **designer**
> (`hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M`), comme un agent générique classique.
> *(Historique : ce rôle était tenu par `moondream`, ~1,4 Go, retiré car non réassigné
> après ce remplacement — voir le README, section 🖼️ Vision.)*

> `hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M` (embeddings, ~0,6 Go) équipe la recherche vectorielle (RAG),
> pas un agent de chat.

> ⚠️ Ne pas confondre avec le champ `"model"` de `config/agent_profiles.json` : c'est le
> modèle **par défaut du profil** (persona/prompt), affiché dans l'onglet Agents avant
> toute réassignation. Le modèle **effectivement utilisé** en chat est celui ci-dessus,
> tant qu'aucune réassignation n'a été faite pour l'agent concerné.

Les modèles peuvent être changés via l'onglet **Agents** dans l'interface web ou l'API `/api/agents/assign`.
