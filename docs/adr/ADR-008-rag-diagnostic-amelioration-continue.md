# ADR-008 : RAG d'amélioration continue pour les pipelines de diagnostic

**Statut :** Proposé (non implémenté — descriptif pour amélioration future)
**Date :** 24/07/2026
**Décideur :** Michel

## Contexte

JARVIS possède déjà une famille de pipelines de diagnostic métier, définis en
YAML et exécutés par `services/pipeline.py` :

| Pipeline | Fichier | Fonction |
|---|---|---|
| `network_triage` | `config/pipelines/network_triage.yaml` | Analyse problème réseau → cause racine → script de correction |
| `diagnostic_drone_vision` | `config/pipelines/diagnostic_drone_vision.yaml` | Image drone → diagnostic matériel → rapport |
| `incident_response` | `config/pipelines/incident_response.yaml` | Incident sécu → analyse → remédiation → post-mortem |
| `full_audit` | `config/pipelines/full_audit.yaml` | Audit système + réseau + sécurité |
| `code_review` | `config/pipelines/code_review.yaml` | Script → revue de code → audit sécu |
| `security_audit` | `config/pipelines/security_audit.yaml` | Audit sécurité dédié |

Ces pipelines existent et sont câblés (chargés et exécutés par
`PipelineService`), mais fonctionnent en **enchaînement séquentiel de prompts
LLM sans aucune mémoire des cas passés** : `services/pipeline.py` ne fait
aucun appel à `services/vector.py`. Chaque diagnostic repart de zéro, même si
un cas quasi identique a déjà été traité et corrigé la veille.

En parallèle, une brique de recherche sémantique existe déjà
(`services/vector.py`, `context["similar_cases"]`, consommée par
`agents/base.py::_similar_cases_block`) mais n'est reliée à aucun de ces
pipelines de diagnostic, et est aujourd'hui **cassée** (mismatch de clé
`vector_results`/`similar_cases` dans `services/pipeline_steps.py`, cf. audit
du 22/07/2026, chantier distinct déjà tracé dans `ROADMAP.md` Phase 3).

### Objectif initial (retracé de mémoire, ~4 mois de travail)

L'intention de départ était de s'inspirer du principe de
[`karpathy/autoresearch`](https://github.com/karpathy/autoresearch) : une
boucle qui **mesure, garde ce qui améliore, jette ce qui n'améliore pas, et
recommence**. Dans ce repo, la boucle porte sur des poids de modèle
(fine-tuning). Le choix pour JARVIS était d'appliquer le même principe de
boucle à la **récupération** (RAG) plutôt qu'au **fine-tuning** (QLoRA/PEFT
Hugging Face), le corpus de documents disponible étant insuffisant pour un
fine-tuning pertinent. Cette intention n'a jamais été implémentée sous cette
forme : au fil des sessions de debug de l'existant, seule la brique de
récupération passive (`similar_cases`) a été posée, sans la boucle de mesure
qui en faisait l'intérêt — et cette brique elle-même s'est cassée en route.

## Décision proposée

Construire une boucle d'amélioration continue **au-dessus** des pipelines de
diagnostic existants, sans toucher aux poids du modèle :

### 1. Capitalisation (après chaque exécution de pipeline diagnostic)
- À la fin d'un pipeline (`network_triage`, `incident_response`, etc.),
  vectoriser le couple `(problème initial, diagnostic produit, correction
  proposée)` dans l'index vectoriel existant (`services/vector.py`), avec les
  métadonnées : pipeline_id, horodatage, feedback utilisateur (👍/👎 déjà
  existant via `sendFeedback`/`sendImplicit`).
- Réutilise l'infrastructure de vectorisation déjà présente
  (`index_message`/`ingest_message`), pas de nouveau service à créer.

### 2. Récupération (au début d'un nouveau diagnostic)
- Avant de lancer un pipeline, interroger `VectorService.search()` pour
  retrouver les cas similaires déjà traités.
- Injecter ces cas dans le prompt de la première étape du pipeline (déjà le
  rôle prévu de `context["similar_cases"]` / `_similar_cases_block` — il
  suffit de le câbler dans `services/pipeline.py`, qui ne l'appelle
  actuellement pas).
- **Pré-requis bloquant :** corriger d'abord le mismatch de clé
  `vector_results`/`similar_cases` (chantier déjà identifié, Phase 3 du
  ROADMAP existant) — cette étape ne peut pas être sautée.

### 3. Mesure (le "val_bpb" de JARVIS)
- Définir une métrique de qualité de diagnostic mesurable automatiquement,
  par exemple : le feedback 👍/👎 déjà collecté, ou si un même problème
  revient (`msg_count`/similarité élevée avec un cas récent marqué 👎 = signe
  que la correction précédente n'a pas tenu).
- Sans cette métrique, il n'y a pas de "garder/jeter" possible — c'est la
  pièce manquante la plus critique, à spécifier avant tout code.

### 4. Garder / jeter (consolidation orientée qualité)
- `VectorService.consolidate()` existe déjà mais ne fait que du
  dédoublonnage/élagage générique par poids et ancienneté — **pas** une
  évaluation de pertinence diagnostic.
- Étendre cette consolidation (ou créer une passe dédiée) pour repondérer les
  cas vectorisés en fonction de la métrique du point 3 : renforcer les cas
  qui ont mené à un 👍 durable, faire décroître ceux qui ont mené à un 👎 ou
  une récidive.

## Conséquences

- ✅ Répond à la contrainte initiale (corpus trop petit pour QLoRA/PEFT) sans
  changer d'approche technique.
- ✅ Réutilise à 100% l'infrastructure déjà posée (vector.py, feedback,
  pipelines YAML) — pas de nouveau service lourd.
- ⚠️ Dépend strictement de la correction préalable du bug RAG existant
  (Phase 3 du ROADMAP) — à faire avant, pas en parallèle.
- ⚠️ Le point le plus flou à trancher avant tout code : la métrique de
  qualité du point 3. Sans elle, cette ADR reste une intention, pas un plan
  exécutable.
- ❌ Ne pas confondre avec le fine-tuning : cette boucle n'améliore jamais le
  modèle lui-même, seulement ce qu'on lui donne à lire.

## Modules impactés (si acceptée)

- `services/pipeline.py` — brancher un appel `VectorService.search()` avant
  la première étape, et un appel de vectorisation après la dernière.
- `services/vector.py` — étendre `consolidate()` avec repondération par
  feedback (ou nouvelle méthode dédiée).
- `services/pipeline_steps.py` — corriger d'abord le mismatch de clé
  (pré-requis, hors périmètre de cette ADR).
- `config/pipelines/*.yaml` — pas de changement de structure a priori, la
  récupération s'insère en amont sans modifier le format des steps.

## Voir aussi

- ROADMAP.md, Phase 3 (bug RAG à corriger en premier).
- ADR-005 (pipeline RAG runbooks — à réviser/remplacer, décrit un design
  différent et un fallback histogramme aujourd'hui supprimé).
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — source
  d'inspiration du principe mesurer/garder/jeter, appliqué ici à la
  récupération plutôt qu'au fine-tuning.
