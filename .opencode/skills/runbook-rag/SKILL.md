---
name: runbook-rag
description: >
  Use when working on JARVIS's runbook ingestion/search pipeline (services/vector.py,
  services/sanitize.py, RUNBOOK.md indexing). Trigger this whenever the user asks to
  add incremental runbook indexing, PII/secret scrubbing on queries, service-scoped
  search, or anything related to "runbooks → relevant excerpts" retrieval. Also use
  when extending VectorService or adding a new pipeline step that needs to fetch
  scrubbed runbook context.
---

# Runbook RAG — Ingestion & Search

Pipeline en deux phases : **ingestion** (une fois, incrémentale) et **recherche**
(à chaque incident, scrubbée). Étend `services/vector.py`, n'invente pas un nouveau
service parallèle.

## État actuel vs cible

| Étape du schéma | Existe dans `vector.py` | À ajouter |
|---|---|---|
| Parse + hash | ❌ dédup par texte exact (`_exists`) | Hash de fichier/chunk pour skip si inchangé |
| Embed new/changed | ✅ `_embed` (Ollama + fallback histogramme 16 bins) | Marquer hash dans `Document.metadata` |
| Vector cache | ✅ `memory/vector_index.json` + cache LRU mémoire (`_cache`, TTL 300s) | — |
| Scrub PII/secrets | ❌ inexistant | Créer `services/sanitize.py` |
| Embed query | ✅ `_embed` réutilisable tel quel | — |
| Cosine top-K + service filter | ✅ cosinus dans `_compute_scores` | Filtre `metadata["service"]` avant tri |
| Scrubbed excerpts | ❌ retourne `Document` brut | Passer par `sanitize.py` avant retour |

## Phase 1 — Ingestion (`RUNBOOK.md` → `vector_index.json`)

1. Parser `docs/RUNBOOK.md` en chunks (titre de section = unité naturelle).
2. Hasher chaque chunk (`hashlib.sha256`), stocker dans `metadata["hash"]`.
3. Avant d'appeler `index()` / `index_batch()`, comparer le hash au hash déjà stocké
   pour ce `metadata["source"]` — skip si identique (évite de ré-embedder tout
   le fichier à chaque run, cf. le `_exists` actuel qui ne fait que comparer le texte).
4. `vectorize_pending()` reste le point d'entrée pour générer les embeddings manquants.

## Phase 2 — Recherche (à chaque incident)

1. **Scrub avant tout** : la requête utilisateur passe par `sanitize.scrub(text)`
   AVANT d'être embedée. Ne jamais indexer/logguer la requête brute si elle peut
   contenir des secrets glissés par l'opérateur.
2. `VectorService._embed(scrubbed_query)` pour le vecteur de requête.
3. Dans `_compute_scores`, ajouter un filtre optionnel `service: str | None` :
   ignorer les docs dont `metadata.get("service") != service` si fourni.
4. Trier par cosinus, garder `top_k`, puis **scrubber aussi les excerpts retournés**
   (un runbook peut contenir des credentials en exemple).

## `services/sanitize.py` — à créer

Contrat minimal attendu (le service n'existe pas encore, c'est le principal gap) :

```python
def scrub(text: str) -> str:
    """Masque emails, IPs privées, tokens type AKIA/sk-/ghp_, et patterns
    'password=', 'api_key=' suivis d'une valeur. Retourne le texte avec
    [REDACTED] à la place. Ne doit jamais lever d'exception sur texte vide."""
```

Tester sur des cas réels : logs avec IP, snippets `.env`, tokens Ollama/API.

## Intégration pipeline (optionnel)

Si ce RAG doit être appelé depuis un pipeline (cf. `config/pipelines/incident_response.yaml`
comme référence de format), ajouter un step avant `triage` :

```yaml
- name: fetch_context
  agent_key: rag
  prompt_template: "Contexte runbook pertinent pour : {task}"
  on_error: skip
```

`agent_key: rag` n'existe pas encore dans `config/agent_routing.yaml` — à créer s'il
n'y est pas, ou réutiliser `dev` en attendant.

## Règles de code (héritées de team-jarvis)

- 1 fonction = 1 responsabilité (le futur `sanitize.py` ne doit pas vectoriser).
- Pas de service parallèle à `VectorService` — étendre, ne pas dupliquer.
- Toute nouvelle clé de `metadata` (`hash`, `service`) doit être documentée ici.
