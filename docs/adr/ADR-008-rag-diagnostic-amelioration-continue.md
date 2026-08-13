# ADR-008 : RAG d'amélioration continue pour les pipelines de diagnostic

**Statut :** Accepté — implémentation en cours (Phase S puis Phase 7)  
**Date :** 2026-07-24  
**Décideur :** Tech Lead + équipe JARVIS  

## Contexte

Le pipeline RAG existant (ADR-005) injecte des cas similaires dans le prompt
du LLM pour améliorer les diagnostics. Cependant, il ne tire aucun
enseignement de ses propres résultats :

1. Aucune capitalisation des diagnostics passés (erreurs, feedbacks,
   scores) — chaque exécution repart de zéro.
2. Aucune rétropropagation de score vers les chunks de la base vectorielle
   — un chunk qui produit systématiquement de mauvais diagnostics n'est
   jamais pénalisé ni élagué.
3. Pas de boucle adaptative : si le diagnostic est insuffisant, le pipeline
   ne fait pas de seconde tentative (HyDE, reformulation).
4. Le score du juge isolé (`LlmResponseJudge`) existe mais n'est pas
   branché sur la capitalisation (codé en dur à `0.0`/`""`).

## Décision

On ajoute au pipeline RAG existant un **système d'amélioration continue**
en 4 briques indépendantes, chacune derrière son port (Protocol).

### Brique 1 — Sidecar JSONL (trace quotidienne)

Chaque exécution de pipeline produit un `TraceRecord` persisté dans un
fichier JSONL quotidien (`traces/pipelines/YYYY-MM-DD.jsonl`).

- **Port :** `ITraceStore.append(record: TraceRecord) -> None`
- **Format :** une ligne JSON par trace, mode ajout (pas d'écrasement —
  corrigé Phase S.2)
- **Contenu :** `trace_id`, `pipeline_id`, `query`, `retrieved_chunk_ids`,
  `judge_score`, `judge_reason`, `timestamp`, `feedback`

### Brique 2 — Score composite

Le score final pour la rétropropagation combine :

```
composite = 0.6 * judge_score + 0.4 * feedback_score
```

Avec :
- `judge_score` : sortie du `IResponseJudge.evaluate()` (0.0 à 1.0)
- `feedback_score` : `1.0` si 👍, `0.0` si 👎, `0.5` si absent
- `recidive` : booléen (même erreur que la trace précédente) → pénalité
  `-0.3` si vrai

### Brique 3 — Rétropropagation par chunk

`VectorService` expose deux nouvelles opérations :

- `update_score(chunk_id: str, delta: float)` — incrémente le score
  cumulé d'un chunk (positif si bon résultat, négatif si mauvais)
- `consolidate()` — élague les chunks toxiques (score < `SCORE_PRUNING_THRESHOLD`
  (`-2.0`) ou `bad_count > BAD_COUNT_PRUNING_THRESHOLD` (`3`))

Les seuils sont des constantes nommées dans `config/constants.py` :
- `SCORE_PRUNING_THRESHOLD = -2.0`
- `BAD_COUNT_PRUNING_THRESHOLD = 3`

### Brique 4 — Boucle adaptative (HyDE + retry + arrêt mécanique)

```python
for attempt in range(max_attempts):
    checkpoint_sidecar()                      # avant chaque tentative
    response = generate(query, similar_cases)
    score = judge.evaluate(query, chunks, response)
    if score >= JUDGE_THRESHOLD: break         # arrêt sur qualité suffisante
    if stagnation_detected(attempt): break     # arrêt sur stagnation mécanique
    query = build_hyde_query(query, response)  # reformulation HyDE au 2ᵉ essai
```

- `max_attempts = 3` (constante nommée)
- `JUDGE_THRESHOLD = 0.8` (constante partagée avec `rag_judge.py`)
- Stagnation : 2 tentatives consécutives avec la même `judge_reason`
- HyDE : la réponse précédente est utilisée comme pseudo-document pour
  reformuler la requête

## Décisions dérivées (D1–D11)

| ID | Décision | Justification |
|----|----------|---------------|
| D1 | Les traces sont stockées en JSONL (pas SQLite, pas CSV) | Append-only, ligne = 1 record, lisible sans outil, compatible avec l'existant (fichiers plats) |
| D2 | Un fichier par jour calendaire (pas 1 fichier global) | Évite la dérive taille fichier, backup naturel par date |
| D3 | `TraceRecord` est un dataclass frozen, pas un dict | Contrat de type explicite, hashable, sérialisable via `asdict()` |
| D4 | Le juge isolé (`IResponseJudge`) est un port séparé (pas noyé dans le pipeline) | SRP — le pipeline ne sait pas COMMENT on juge, il utilise le port |
| D5 | Le juge ne voit pas le raisonnement de l'acteur (uniquement requête + chunks + réponse) | Isolation Verifier Sub-Agent (SKILL.md §6) |
| D6 | `JUDGE_THRESHOLD = 0.8` en constante partagée | Cohérence pipeline / juge, modifiable sans refonte |
| D7 | Score composite = weighted average de 2 sources (pas de ML) | KISS — une formule linéaire est suffisante et testable unitairement |
| D8 | Rétropropagation au niveau chunk (pas document) | Plus granulaire, permet d'élaguer des chunks précis sans perdre le document entier |
| D9 | `consolidate()` est une méthode synchrone, pas un background job | Mono-utilisateur offline (ADR-007), pas de besoin de file d'attente |
| D10 | Boucle adaptative max 3 essais (pas de while True) | Évite les boucles infinies, condition d'arrêt mécanique vérifiable par assertion |
| D11 | Checkpoint sidecar AVANT chaque tentative (pas seulement à la fin) | Cohérent avec loop-engineering.md — principe de checkpoint avant effet de bord irréversible |

## Conséquences

**Positives :**
- Les diagnostics passés capitalisent via la trace JSONL (exploitable pour
  fine-tuning futur).
- Les chunks toxiques sont automatiquement élagués.
- Le pipeline s'auto-améliore sans intervention humaine.
- Chaque brique est testable isolément (ports + mocks).

**Négatives :**
- Complexité ajoutée au pipeline (boucle adaptative, checkpoints).
- La rétropropagation nécessite une `consolidate()` périodique (coût
  O(n) sur l'index).
- La boucle adaptative peut multiplier par 2–3 le temps d'exécution d'un
  pipeline en cas de scores bas.

## Implémentation

### Phases

| Phase | Contenu | Fichiers concernés | Dépendances |
|-------|---------|-------------------|-------------|
| S     | Stabilisation : LLMAdapter, trace_sidecar, ADR-008 | `protocols.py`, `trace_sidecar.py` | Aucune |
| 7.1   | Brancher juge isolé sur capitalisation | `pipeline.py` | S.1, S.2 |
| 7.2   | Score composite | `config/constants.py`, `pipeline.py` | 7.1 |
| 7.3   | Rétropropagation par chunk | `vector.py`, `config/constants.py` | 7.2 |
| 7.4   | Boucle adaptative HyDE + retry | `pipeline.py` | 7.3 |

### Ports impliqués (inchangés après S.1)

Tous dans `services/adapters/protocols.py` :
- `LLMAdapter` — génération de texte et multimodal (restauré S.1)
- `ITraceStore` — persistance des traces
- `IVectorSearch` — recherche et bientôt rétropropagation
- `IResponseJudge` — évaluation isolée de la qualité réponse

\newpage