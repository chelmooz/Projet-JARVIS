# Roadmap — Knowledge Base structurée & Intégration Triad (JARVIS)

**Date** : 2026-08-16/17 · **HEAD** : `734616e` · **Nature** : synthèse documentaire
(confrontation conversation ↔ code réel). Aucune ligne de code métier modifiée.

> **Convention de preuve** : toute affirmation est accompagnée d'une preuve
> (`fichier:ligne`, commit, entrée BACKLOG ou ADR). Toute piste non prouvée est
> marquée **[NON VALIDÉ PAR CODE]** et ne devient planifiable qu'après jalon de
> décision utilisateur (section 3) — jamais sur une « intention supposée ».

---

## 0. État des lieux (preuves)

### 0.1 Triad Lot 12 — ce qui existe réellement

| Fait constaté | Preuve |
|---|---|
| `run_pipeline(question: str)` — entrée = **simple question**, zéro chunks, zéro réponse à évaluer | `agents/orchestrator.py:40-42` ; prompts `_judge_prompt(question)` l.14-15, `_advocate_prompt(question, judge_dict)` l.18, `_evaluator_prompt(question, judge, advocate)` l.28 |
| Boucle revise `run_pipeline_with_revision(question, max_revisions=2)` → `(result, revisions_count)` | `agents/revision.py:9-11` ; déviation L7 documentée BACKLOG l.42-47 |
| Contrats Pydantic `JudgeOutput` / `AdvocateOutput` / `EvaluatorOutput` | `agents/eval_contracts.py:14-45` (L2, commit `fce2cb7`) |
| Prompts SKILL judge/advocate/evaluator (copies de `H:\ref-rag`) | `agents/skills_eval/` + `load_skill_eval` (L3) ; source `H:\ref-rag` présent sur disque |
| Client Ollama `generate_json` + `unload` (HTTP mocké dans les tests) | `agents/ollama_client.py:21-60` (L4, commit `fce2cb7`) |
| `CyberEvalService.analyze(question, max_revisions=2)` → `{decision, score, reasoning, revisions}` fail-closed | `services/cyber_eval_service.py:16-35` (L7, commit `0b77e08`) |
| Port `CyberEvalPort` (Protocol, jamais None) | `ports/cyber_eval_port.py:8-22` |
| Route `POST /api/cyber/analyze` + `AnalyzeRequest` Pydantic + singleton lazy | `controllers/routes/cyber_eval.py:16-39` (L8, commit `4dbb46d`) ; BACKLOG l.9-32 |
| Tests triad : 100 % mockés, zéro appel Ollama réel | `tests/test_cyber_eval_routes.py`, `tests/test_cyber_eval_service.py` (5+5 tests) ; BACKLOG L4-L8 |
| **Aucune entrée « MT-Lot12-L9 » dans le BACKLOG** (L1→L8 seulement) | `BACKLOG.md` — section Lot 12 |
| Mémo de passation : « L7-L9 : intégration dans pipeline cyber » = travail **futur**, non détaillé, non planifié | Mémo de passation utilisateur (section « Reprendre Lot 12 L4-L9 ») |

### 0.2 RAG de production (ADR-008) — ce qui existe réellement

| Fait constaté | Preuve |
|---|---|
| Juge RAG isolé `LlmResponseJudge.evaluate(query, chunks, response)` → `{score, reason}`, `JUDGE_THRESHOLD = 0.8` | `services/rag_judge.py:18, 49-68` |
| Juge branché **en production** : boucle adaptative + capitalisation trace | `services/pipeline.py:149` (`judge.evaluate(query, chunk_texts, final_response)`), `:356` ; `import JUDGE_THRESHOLD` l.23 |
| 4 briques ADR-008 : trace sidecar JSONL, score composite `0.6·judge + 0.4·feedback`, rétropropagation chunk, boucle HyDE max 3 | `docs/adr/ADR-008-rag-diagnostic-amelioration-continue.md` (D1-D11, briques 1-4) |
| `VectorService.update_score` / `consolidate` / `search` | `services/vector.py:353, 378, 463` |
| Injection brute des chunks (aucun re-ranking) | `services/pipeline.py:121-122, 176` (`similar_cases` passés dans `ctx`) |

### 0.3 Piste « Knowledge Base » — ce qui n'existe PAS

| Fait constaté | Preuve |
|---|---|
| **Zéro référence** à graphify / lazygraph / LazyGraph / wiki / okf / OKF / WikiService / wikify dans tout le repo | `grep` sur `*.{py,md,toml,yaml,json}` → 0 résultat |
| **Aucun dossier** `wiki/`, `okf/`, `memos/` sur disque | `dir` → inexistants |
| Obsidian / Graphify / LazyGraphRAG : jamais installés, jamais testés | aucune trace dans `requirements.lock`, `pyproject.toml`, `.github/` |
| Mémo datasets par agent (mapping cyber/dev/network/hardware/vision) — **non commité** | `docs/dossier projet dataset/DATASETS_JARVIS_PAR_AGENT.md` (untracked, `git status` `??`) |
| Piste « Lot 13 — Autoresearch (vrai) » (karpathy/autoresearch, keep/discard git, métrique = score moyen triad) | Mémo de passation utilisateur, section « Futur (Lot 13) » — **non commité, non détaillé** |
| Fine-tuning : écarté explicitement (overkill ; prompts SKILL d'abord, fine-tuning léger 1 modèle en réserve) | Analyse utilisateur fournie (3 phases, verdict) |

### 0.4 Contexte architectural (inchangé)

| Fait constaté | Preuve |
|---|---|
| MVC + Ports (pas de Clean Architecture) | `docs/adr/ADR-001-architecture-mvc-ports.md` |
| Backend unique Ollama, 100 % offline, mono-utilisateur | `docs/adr/ADR-007-securite-offline-single-backend.md` ; `README.md:20-24` |
| Sandbox fichiers fail-closed | `docs/adr/ADR-011-sandbox-fail-closed.md` |
| PipelineService = source unique d'exécution de pipeline | `docs/adr/ADR-013-pipeline-source-unique.md` |
| 5 agents : `@cyber` `@dev` `@network` `@hardware` `@vision` | `README.md:32, 148-154` ; mapping `agents/factory.py` (mémo datasets) |
| Lot 11 (Extended FS) : R1-R6 + re-audit **GO 5/5**, 901 passed | `BACKLOG.md` MT-Lot11-L1R1→L1R5 (commit `9b9470d`) |
| Lot 12 : L1-L8 commités, **910 passed / 0 failed**, couverture 83,18 % | `BACKLOG.md` MT-Lot12-L1→L8 (HEAD `4dbb46d`) |

### 0.5 Incident de spécifications inventées (garde-fou, à ne pas effacer)

Dans la conversation précédente, l'IA dev senior (Qwen) a :
1. **Inventé** un endpoint `/api/cyber/analyze` sans validation → **régularisé ensuite** par la
   méthode (décisions validées BACKLOG L8 + commit `4dbb46d`) ;
2. **Créé** `CyberEvalService` sans spécification validée au départ → **régularisé** (BACKLOG L7,
   commit `0b77e08`) ;
3. **Affirmé** que « L7-L9 = intégration pipeline cyber » était un plan documenté — faux :
   le BACKLOG ne contient aucune entrée L9 (section 0.1) ; le mémo de passation ne liste
   « L7-L9 » que comme travail futur ;
4. **Proposé** des phases (OKF, LazyGraphRAG, Graphify, Obsidian…) sans vérifier leur faisabilité
   → aucune trace dans le code (section 0.3).

**Conséquence méthodologique** : les phases 1-5 ci-dessous sont des **propositions de la
conversation**, pas des plans validés. Elles ne deviennent exécutables qu'après jalon de décision
(section 3) et validation empirique des outils externes.

---

## 1. Le problème à résoudre

### 1.1 RAG actuel = injection brute

Les cas similaires sont injectés tels quels dans le contexte du LLM
(`services/pipeline.py:121-122, 176`) : pas de re-ranking, pas de hiérarchie de concepts, risque
de *lost-in-the-middle*, coût tokens croissant avec le nombre de chunks. Le juge
(`rag_judge.py`) note le résultat mais n'a aucune structure de connaissance au-dessus des chunks.

### 1.2 Le triad existe mais n'est PAS branché sur du contexte réel

`run_pipeline(question)` (orchestrator.py:40-42) ne reçoit **ni chunks, ni réponse à évaluer** :
les 3 agents jugent une question « nue ». Le juge n'a donc rien à vérifier — `JudgeOutput.flags`
(`hallucination_suspect`, `omission_source`, `contradiction_interne`, `eval_contracts.py:20-22`)
et `AdvocateOutput.missing_context` (`eval_contracts.py:33`) sont structurellement inexploitables
en l'état. À l'inverse, `rag_judge.py` (production, ADR-008) juge une réponse RAG réelle.
**Deux juges coexistent sans comparaison.**

### 1.3 Rappel de l'incident de justification inventée (traçabilité)

Le lien « triad ↔ pipeline cyber (L7-L9) » a été présenté comme un plan documenté alors qu'il
n'existait pas dans le BACKLOG. Cette roadmap pose la règle inverse : **toute intégration future
doit référencer une décision actée (section 2) ou un jalon de décision (section 3)** — jamais
une intention supposée. Le point d'incident est consigné en 0.5 et rappelé en section 7.

---

## 2. Décisions déjà actées (à ne pas rouvrir)

| # | Décision | Preuve |
|---|----------|--------|
| D1 | Endpoint dédié `POST /api/cyber/analyze`, body `{"question": str, "max_revisions": int = 2}` (validation Pydantic, 422 natif) | commit `4dbb46d` ; BACKLOG l.9-15 ; `controllers/routes/cyber_eval.py:16-21` |
| D2 | Singleton service lazy (pattern `extended_files.py`) | BACKLOG l.10 ; `cyber_eval.py:23-33` |
| D3 | Réponse = dict de `analyze()` directement, pas d'Envelope | BACKLOG l.11 ; `cyber_eval.py:37-39` |
| D4 | Nouveau `CyberEvalPort` + `CyberEvalService` ; `reject` fail-closed si pipeline échoue | BACKLOG L7 l.34-41 ; `ports/cyber_eval_port.py:8-22` ; `cyber_eval_service.py:20-26` |
| D5 | `run_pipeline_with_revision` retourne `(result, revisions_count)` | BACKLOG l.42-47 (déviation L6 actée) |
| D6 | Triad : enchaînement strict judge → advocate → evaluator, prompts par concaténation, `None` si un agent échoue | BACKLOG L5 l.89-98 ; `orchestrator.py:40-69` |
| D7 | Client Ollama : `generate_json` (timeout 120 s) + `unload` (10 s), aucune exception ne fuit | BACKLOG L4 l.117-139 ; `ollama_client.py` |
| D8 | Sandbox fichiers fail-closed : absence de config ⇒ refus formel | ADR-011 ; `file_system.py` |
| D9 | Backend unique Ollama, offline, mono-utilisateur ; zéro cloud | ADR-007 |
| D10 | Architecture MVC + Ports, composition root `jarvis.py` + `controllers/router.py` | ADR-001 |
| D11 | PipelineService = source unique d'exécution de pipeline | ADR-013 |
| D12 | `rag_judge.py` = juge RAG de production, `JUDGE_THRESHOLD = 0.8`, boucle adaptative ADR-008 | `rag_judge.py:18` ; `pipeline.py:149, 153` ; ADR-008 |
| D13 | Mapping datasets par agent (cyber/dev/network/hardware/vision) | `docs/dossier projet dataset/DATASETS_JARVIS_PAR_AGENT.md` (validation utilisateur, **fichier non commité**) |
| D14 | Fine-tuning spécialisé multi-modèles = hors périmètre (analyse utilisateur : overkill, 8-32 h GPU) | Analyse utilisateur fournie (Phase 3 = « OVERKILL, à éviter ») |

---

## 3. Décisions ouvertes — tranchées par l'utilisateur (2026-08-17)

| # | Décision | Tranchement | Justification (Dev Senior) |
|---|----------|-------------|----------------------------|
| O1 | Mode d'intégration triad | ✅ **shadow (log only)** | `rag_judge.py` en production (ADR-008) non remplacé sans comparaison mesurée ; shadow = parallèle, logue sans agir ; après 2-4 semaines → comparer sur 100+ questions, puis garder/remplacer/compléter. Risque éliminé : zéro régression production |
| O2 | Backend LazyGraphRAG | ✅ **adapter `VectorService` existant** | KISS : `search`/`update_score`/`consolidate` existent (`vector.py:353, 378, 463`) ; ajouter `traverse(concept) -> list[Page]` (embeddings → filtre `links_to` → top-k + voisins) ; lib externe (Microsoft GraphRAG) = overkill (8 h indexation), nouvelle dépendance, risque ADR-007 offline |
| O3 | Portage Obsidian 3 plateformes | ⏳ **validation empirique d'abord** (plan tranché, choix d'outil suspendu au test) | Télécharger Portable (Win) / `.app` (macOS) / AppImage (Linux), tester sur clé USB (graphe fonctionnel) ; si OK → `tools/obsidian/` + `launch_obsidian.py` ; si KO → markdown brut + visualisation custom. Aucune preuve de faisabilité dans le repo |
| O4 | Priorité datasets | ✅ **cyber (MITRE ATT&CK) en premier** | Cœur de JARVIS = audit sécurité (`@cyber`) ; STIX JSON structuré (techniques/tactiques déjà organisées) ; ~50 Mo raisonnable. Ordre : 1. MITRE (Phase 1) → 2. CodeSearchNet (Phase 2) → 3. CAIDA → 4. UCI Grid Stability → 5. COCO (Phase 5) |
| O5 | Pipeline de préparation datasets | ✅ **pré-calcul GPU externe + import `.parquet`** | Qwen2.5-7B CPU = 1-2 h pour 1000 entrées vs 5-10 min sur RTX 4000+ ; `prepare_dataset.py` (JSONL → chunk → embeddings nomic GPU → `chunks.parquet` + `embeddings.parquet`) copiés sur clé USB, chargement instantané sans LLM ; Phase 2 : script d'ingest embarqué (plus lent, autonome) |
| O6 | Forme de la knowledge base | ✅ **LLM Wiki Karpathy (pas Autoresearch)** | LLM Wiki = pages markdown structurées + liens sémantiques, Obsidian pour visualiser, exploitable par traversal programmatique ; Autoresearch (mémo Lot 13) = outil d'optimisation des prompts SKILL (keep/discard git), **pas une KB** ; complémentaires : KB en Phases 1-5, Autoresearch plus tard (Lot 13) |

> Les phases marquées **[NON VALIDÉ PAR CODE]** ci-dessous sont désormais **planifiables**
> (décisions O1-O6 tranchées le 2026-08-17), sauf O3 (choix Obsidian suspendu au test
> empirique). Le marquage reste en vigueur jusqu'à ce qu'un code réel existe.
> Aucune implémentation sans BACKLOG + validation utilisateur (règle absolue).

---

## 4. Architecture cible (diagramme texte)

```text
Sources (JSONL, 1 dataset par agent — D13)
        │  ingest (manuel Phase 1 → automatisé Phase 2)
        ▼
LLM Wiki (okf/ ou wiki/ — décision O6)
  pages/concepts · pages/procedures · SCHEMA.md · log.md
        │
        ├──► index vectoriel (VectorService, embeddings nomic — existant, vector.py)
        └──► graphe de liens sémantiques (LazyGraphRAG — décision O2, [NON VALIDÉ])
                      │
                      ▼
AgentGraph / PipelineService (existant, ADR-013)
  retrieval chunks + pages wiki liées
        │
        ▼
Triad judge → advocate → evaluator (existant, orchestrator.py)
  run_pipeline(question, chunks, wiki_pages)  ← branchement à faire (Phase 3)
  mode : décision O1 (shadow proposé par la conversation, non acté)
        │
        ▼
rag_judge.py (ADR-008, production, INCHANGÉ en mode shadow)
  score composite + trace sidecar + rétropropagation (pipeline.py:149, 353-368)
```

---

## 5. Phases détaillées

> Chaque phase : objectif, prérequis (dépendances + décisions ouvertes), livrable vérifiable,
> critère de sortie, risques issus de la conversation.

### Phase 0 — Audit datasets

- **Objectif** : valider la faisabilité des 5 datasets candidats (un par agent) et produire des
  sous-ensembles JSONL exploitables.
- **Prérequis** : aucun code. S'appuie sur `DATASETS_JARVIS_PAR_AGENT.md` (D13, non commité) et
  ADR-008 (la capitalisation consommera ces sources).
- **Livrable** : tableau d'audit (taille réelle, format, licence, représentativité) + 5 fichiers
  `wiki/sources/*.jsonl` (≤ 1000 entrées chacun, sous-ensembles).
- **Critère de sortie** : 5 JSONL validés humainement, cohérents avec le mapping D13 ;
  datasets massifs (Common Crawl, The Pile — mémo D13) écartés ou échantillonnés.
- **Risques** : volumes massifs (D13 liste des datasets 10/10 multi-To), formats hétérogènes
  (STIX pour MITRE ATT&CK, CSV, JSON imbriqué) ; MITRE nécessite une conversion STIX → JSONL.

### Phase 1 — MVP LLM Wiki (1 dataset, ingest manuel, Obsidian) — **[NON VALIDÉ PAR CODE]**

- **Objectif** : créer la structure wiki et ingérer manuellement MITRE ATT&CK (O4 tranchée)
  pour valider le format avant toute automatisation.
- **Prérequis** : décisions **O4** (MITRE en premier) et **O6** (LLM Wiki Karpathy) tranchées
  (2026-08-17) ; Phase 0 livrée ; validation empirique Obsidian portable (O3 — plan tranché,
  choix d'outil suspendu au test).
- **Livrable** : `wiki/SCHEMA.md` + `wiki/log.md` + 10-15 pages
  (`wiki/pages/concepts/…`, `wiki/pages/procedures/…`) + Obsidian portable ouvrant `wiki/`
  (graphe navigable) + guide `docs/OBSIDIAN_USAGE.md`.
- **Critère de sortie** : graphe Obsidian fonctionnel sur 3 OS (validation empirique O3) ;
  10-15 pages validées humainement ; aucune page créée par le LLM sans relecture.
- **Risques** : Obsidian portable inexistant sur disque (aucune preuve de faisabilité) ;
  qualité des pages LLM (mitigation : validation humaine + lint Phase 4) ; Qwen2.5-7B lent sur
  CPU (ingest manuel = 4-6 h selon la conversation).

### Phase 2 — Automatisation ingest (WikiService) — **[NON VALIDÉ PAR CODE]**

- **Objectif** : automatiser l'ingestion (JSONL → chunk → LLM → pages wiki → liens).
- **Prérequis** : Phase 1 livrée (format wiki figé) ; décision **O5** tranchée (pré-calcul GPU
  externe + import `.parquet` ; script d'ingest embarqué en réserve pour Phase 2).
- **Livrable** : `services/wiki_service.py` (`ingest(dataset_path)`) + `tests/test_wiki_service.py`
  (LLM 100 % mocké, convention repo) ; ingestion des 4 datasets restants (CodeSearchNet, CAIDA,
  UCI Grid Stability, COCO — D13).
- **Critère de sortie** : 50+ pages wiki ; spot-check humain de 10 pages par dataset ; gates
  (ruff + mypy + pytest ≥ 60 %).
- **Risques** : 1000 entrées = 1-2 h sur CPU (pré-calcul GPU externe = décision O5) ;
  hallucinations du LLM sur les pages (lint Phase 4 + validation humaine) ;
  **aucun code existant** : `WikiService` est une création complète, à planifier en micro-tâches
  TDD une fois O5/O6 tranchés.

### Phase 3 — LazyGraphRAG + branchement triad (mode shadow) — **[branchement triad : partiellement ancré]**

- **Objectif** : brancher le triad sur du contexte réel (chunks + pages wiki) et comparer ses
  verdicts à `rag_judge.py` sans modifier le comportement de production.
- **Prérequis** : décisions **O1** (mode shadow) et **O2** (adapter `VectorService`, méthode
  `traverse`) tranchées (2026-08-17) ; Phase 2 livrée.
- **Ancrage code existant** : le triad (orchestrator.py) et le juge RAG (pipeline.py:149)
  existent ; le **branchement** lui-même (faire passer chunks + réponse au triad) n'existe pas —
  c'est le cœur de la phase. `run_pipeline` et `run_pipeline_with_revision` devront évoluer
  (signatures actuelles : `orchestrator.py:40`, `revision.py:9`) avec adaptation des tests L5-L7.
- **Livrable** : extension `VectorService.traverse(concept)` (O2 : embeddings → filtre
  `links_to` → top-k + voisins) + triad recevant
  `(question, chunks, wiki_pages)` + comparaison shadow vs `rag_judge` sur 50 questions réelles +
  rapport `docs/triad-vs-ragjudge-analysis.md`.
- **Critère de sortie** : 50 verdicts comparés ; recommandation documentée
  (garder shadow / remplacer / compléter) ; **`rag_judge.py` strictement inchangé** (ADR-008).
- **Risques** : double coût LLM (triad = 3 appels × révisions) en mode actif — le mode shadow
  l'élimine par conception ; divergence Wiki vs RAG (mitigation : triad reçoit les deux,
  mode shadow pour mesurer) ; surcharge de `run_pipeline` (contrats Pydantic existants à préserver).

### Phase 4 — Optimisation (re-ranking, cache, lint) — **[NON VALIDÉ PAR CODE]**

- **Objectif** : rendre le retrieval wiki efficace et surveiller sa santé.
- **Prérequis** : Phase 3 livrée.
- **Livrable** : `services/wiki_ranker.py` (pertinence, fraîcheur, liens) + `services/wiki_cache.py`
  (LRU, TTL 1 h) + `services/wiki_monitor.py` + `scripts/wiki_lint.py` (pages orphelines,
  contradictions) + rapport hebdomadaire `docs/wiki-health-report.md`.
- **Critère de sortie** : ordre des pages vérifié par tests ; cache hit/miss vérifié ; lint sans
  faux positif sur le corpus Phase 2.
- **Risques** : sur-ingénierie (KISS — la conversation le rappelle pour chaque brique) ;
  cache = cohérence Wiki vs RAG à re-vérifier après TTL.

### Phase 5 — Expansion datasets (par agent : cyber/dev/network/hardware/vision) — **[NON VALIDÉ PAR CODE]**

- **Objectif** : enrichir la wiki par agent selon le mapping D13 (CIC-IDS2017, UNSW-NB15, SQuAD,
  Alpaca, Google Cloud Trace, NREL Solar Power…).
- **Prérequis** : Phases 0-2 livrées ; décisions **O4** (MITRE en premier) et **O5** (pré-calcul
  GPU externe) tranchées (2026-08-17).
- **Livrable** : 5+ datasets ingérés via `WikiService` (1 dataset/jour selon la conversation) ;
  200+ pages wiki.
- **Critère de sortie** : spot-check humain par dataset ; lint Phase 4 vert ; gates vertes.
- **Risques** : datasets massifs (The Pile 825 Go, C4 To — D13) → échantillonnage obligatoire ;
  dérive de qualité (lint + spot-check) ; rythme 1 dataset/jour dépend de la machine (O5).

### Phase X — Graphify (indexation code JARVIS lui-même, piste parallèle et indépendante) — **[NON VALIDÉ PAR CODE]**

- **Objectif** : visualiser le graphe de dépendances du code JARVIS (piste parallèle, ne bloque
  aucune phase ci-dessus).
- **Prérequis** : **validation empirique** de l'outil externe (aucune trace dans le repo ;
  `pip install` + `graphify . --wiki` à tester sur le poste réel) + décision utilisateur de
  conserver l'outil.
- **Livrable** : `graphify-out/` + wrapper `services/graph_service.py` + tests (query sur graphe).
- **Critère de sortie** : graphe généré et consultable ; wrapper testé avec mocks.
- **Risques** : outil externe jamais installé ni validé (faisabilité inconnue) ; sortie hors
  périmètre ADR-007 si l'outil requiert du réseau (à vérifier) ; chevauchement avec le graphe
  wiki (Phase 3) — à garder séparé.

---

## 6. Ce qu'on ne fait PAS (hors périmètre explicite)

1. **Fine-tuning** (Phase D du mémo original) — écarté par l'analyse utilisateur : overkill pour
   JARVIS (8-32 h GPU, 4 modèles à maintenir). Réserve : fine-tuning léger d'**un seul** modèle
   (Qwen2.5-7B, ex. ultrachat_200k) uniquement si les prompts SKILL (Phase 1 de l'analyse) et
   les Phases 0-4 de cette roadmap s'avèrent insuffisants.
2. **Remplacement direct de `rag_judge.py`** sans phase shadow de comparaison (Phase 3).
   `rag_judge.py` reste le juge de production (ADR-008) tant que la comparaison n'a pas tranché.
3. **Datasets hors périmètre des 5 agents** : médecine, biologie, physique pure, économie,
   astronomie, sciences humaines (exclusions actées dans `DATASETS_JARVIS_PAR_AGENT.md`, Notes).
4. **Datasets massifs non échantillonnés** (Common Crawl, The Pile, C4, GitHub BigQuery) :
   subsets ≤ 1000 entrées uniquement (règle de la conversation, pas de streaming infini).
5. **Aucune phase sans preuve minimale** (fichier / test / BACKLOG / ADR) ni sans jalon de
   décision section 3 : une phase `[NON VALIDÉ]` n'est jamais planifiée directement.

---

## 7. Garde-fous méthodologiques

1. **Toute nouvelle micro-tâche référence une décision de la section 2**, jamais une
   « intention supposée » — cf. incident de justification inventée (section 0.5) : « L7-L9 =
   plan documenté » était faux ; désormais seule une décision actée ou un jalon O1-O6
   débloque une micro-tâche.
2. **Toute divergence entre code réel et roadmap doit être signalée avant d'avancer**
   (cf. incident CyberEvalService créé sans spécification validée). Le BACKLOG est relu avant
   chaque nouvelle étape (AGENTS.md).
3. **Preuve avant assertion** : un fait non vérifiable dans le code est marqué
   `[NON VALIDÉ PAR CODE]` et reste un jalon de décision, pas un plan. Cette discipline a déjà
   fait ses preuves (re-audit L11-R5, 5/5 points prouvés — BACKLOG l.141-157).
4. **Validation empirique des outils externes** (Obsidian, Graphify, LazyGraphRAG éventuel)
   avant toute planification détaillée : pré-déploiement, aucune machine cible disponible,
   aucune dépendance nouvelle sans preuve de fonctionnement.
5. **Gates inchangés** : `ruff check` · `ruff format --check` · `mypy` · `pytest --cov ≥ 60 %` ;
   tests 100 % mockés (zéro appel Ollama/réseau réel) ; commits en conventional commits
   (`feat|fix|docs|test|refactor(scope): MT-LotXX-LY — description`), après validation
   utilisateur uniquement.
6. **Mode shadow acté (O1, 2026-08-17)** pour l'intégration triad : rien ne remplace
   `rag_judge.py` en production sans comparaison mesurée (section 6.2).
7. **Cette roadmap est mise à jour après chaque phase** (état réel, hash de commit, chiffres
   mesurés) — y compris le marquage `[NON VALIDÉ]` qui doit être levé par les preuves réelles.

---

**Fin de la roadmap.** Décisions O1-O6 tranchées (2026-08-17). Prochaine action :
**Phase 0 — Audit datasets** (MT-KB-L0), puis Phase 1 (MVP LLM Wiki MITRE ATT&CK).