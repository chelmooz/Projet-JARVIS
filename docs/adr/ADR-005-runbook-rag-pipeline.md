# ADR-005 — Pipeline RAG pour runbooks

- **Statut :** Accepte
- **Date :** 2026-07-01
- **Auteur :** Data/Secu/Docs (JARVIS)

---

## Contexte

Le systeme JARVIS doit permettre une recherche semantique dans les runbooks (collection de documents Markdown). Les besoins sont :

1. Interrogation en langage naturel sur le contenu des runbooks
2. Indexation incrementale sans re-indexation complete a chaque ajout
3. Fonctionnement degrade si le backend d'embedding (Ollama) est indisponible

Le service VectorService existe deja dans le codebase et assure la gestion des embeddings et de la recherche cosinus. Aucun nouveau service n'est requis.

---

## Decision

### Architecture

```
[User] -> /api/search -> VectorService.search() -> [Response]
                                |
[FileWatcher] -> /api/ingest -> VectorService.add() -> hash dedup -> vector_index.json
```

### Composants utilises

| Composant | Role | Fichier |
|---|---|---|
| VectorService | Embedding + stockage vectoriel + recherche cosinus | `services/vector.py` |
| clean_text | Troncature a 20K caracteres | `services/sanitize.py` |

### Pipeline detaillee

#### Ingestion
1. Fichier detecte par FileWatcher → POST `/api/ingest`
2. `SHA256(content)` calcule le hash du document
3. VectorService verifie si le hash existe deja dans `vector_index.json`
   - Si oui : ignore (ingestion incrementale)
   - Si non : genere l'embedding via Ollama, ajoute a l'index, persiste

#### Recherche
1. Requete utilisateur → POST `/api/search`
2. VectorService convertit la requete en embedding via Ollama
3. Similarite cosinus contre tous les vecteurs de l'index
4. Top-K resultats (configurable, defaut 5)

#### Fallback embedding
- Si Ollama est indisponible : VectorService utilise un histogramme de bytes (16 bins) comme vecteur de repli
- L'embedding Ollama reste le comportement nominal

---

## Consequences

### Positives

- **Recherche vectorielle** : comprehension semantique, pas de simple keyword matching
- **Ingestion incrementale** : le hash SHA256 evite de re-indexer les documents deja connus
- **Pas de nouveau service** : VectorService est reutilise, maintenance centralisee
- **Fallback** : l'histogramme permet un fonctionnement meme sans Ollama

### Negatives

- **Dependance Ollama** : l'embedding nominal necessite Ollama disponible et reactif
- **Fallback degrade** : l'histogramme est moins pertinent que l'embedding semantique
- **Stockage disque** : `vector_index.json` contient les vecteurs en clair

---

## Voir aussi

- **ADR-001** — Architecture generale de JARVIS
- **Skill runbook-rag** — Guide d'utilisation et de test de la pipeline
- **Audit securite RAG** — Analyse des risques secu (`docs/archive/audit-securite-rag.md`)
