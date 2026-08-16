# Audit datasets — Phase 0 (MT-KB-L0)

**Date** : 2026-08-17 · **Méthode** : recherche web + téléchargement de test (aucun
code métier modifié). Chaque fait est daté/vérifié ; les fichiers marqués `[vérifié
par téléchargement]` ont été réellement récupérés sur le poste.

Sources de référence : `docs/dossier projet dataset/DATASETS_JARVIS_PAR_AGENT.md`
(mapping D13, non commité) + décisions O4 (MITRE en premier) et O5 (pré-calcul GPU +
import `.parquet`) — `ROADMAP_KB.md` §3.

---

## 1. Tableau de synthèse

| # | Dataset (agent) | Format | Taille réelle | Licence | Téléchargement | Verdict |
|---|---|---|---|---|---|---|
| 1 | MITRE ATT&CK Enterprise v19.1 (`@cyber`) | STIX 2.1 JSON | 45,3 Mo (repo `mitre/cti`) / 50,8 Mo (`attack-stix-data`) | MITRE ATT&CK Terms of Use — libre (rech./dév./commercial), **attribution obligatoire** | Direct, sans inscription | ✅ **GO** |
| 2 | CodeSearchNet (`@dev`) | JSONL (original) / parquet (HF) | 3,93 Go (4,14 M lignes) ; config `python` = 581 Mo (412 178 ex. train) | **Hétérogène** : licence par dépôt GitHub source (`license: other`, détaillée dans `_licenses.pkl`) ; projet = MIT | Direct (S3/HF), sans inscription | ⚠️ **GO conditionnel** (sous-ensemble licence-auditable) |
| 3 | CAIDA Topology (`@network`) | ITDK / traceroutes | Variable (To) | **CAIDA AUA** : formulaire + licence non transférable, 1 an, usage recherche/gouv ; entreprises = membre payant | Formulaire obligatoire | ❌ **RESTREINT** — incompatible redistribution clé USB |
| 4 | UCI Grid Stability (`@hardware`) | CSV | **2,3 Mo** (10 000 instances, 12 features) `[vérifié par téléchargement]` | CC BY 4.0 (attribution) | Direct, sans inscription | ✅ **GO** |
| 5 | COCO 2017 (`@vision`) | Annotations JSON (+ images 19 Go **non nécessaires**) | `instances_val2017.json` ≈ 25 Mo ; `captions_val2017.json` ≈ 18 Mo ; images = 19 Go (train) | CC BY 4.0 | Direct, sans inscription | ✅ **GO** (annotations seules) |

---

## 2. Détail par dataset

### 2.1 MITRE ATT&CK Enterprise — ✅ GO (priorité O4, Phase 1)

- **Format** : STIX 2.1 (`enterprise-attack.json`), techniques = objets `attack-pattern`,
  organisées par tactique (kill-chain phases), avec descriptions, détections, données
  (data sources), atténuations.
- **Taille réelle** : v19.1 (12 mai 2026) = 45,3 Mo (`github.com/mitre/cti` release
  `ATT&CK-v19.1`) / 50,8 Mo (`mitre-attack/attack-stix-data` v19.1). URL directe :
  `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-19.1.json`
- **Licence** : « MITRE hereby grants you a non-exclusive, royalty-free license to use
  ATT&CK® for research, development, and commercial purposes » — attribution requise
  (« © 2026 The MITRE Corporation. This work is reproduced and distributed with the
  permission of The MITRE Corporation. »), pas d'endossement implicite. Compatible
  redistribution sur clé USB avec mention.
- **Représentativité** : 100+ tactiques/techniques structurées — idéal pour
  `wiki/pages/concepts/` et `wiki/pages/procedures/` @cyber (détection de mouvement
  latéral, etc.).
- **Conversion** : STIX → JSONL (extraire par objet `attack-pattern` : id, name,
  description, tactic, x_mitre_detection, x_mitre_data_sources…). Aucune extraction
  nécessaire pour le téléchargement lui-même.

### 2.2 CodeSearchNet — ⚠️ GO conditionnel (Phase 2)

- **Format** : JSONL multi-part (original GitHub, `script/setup` S3) ; HuggingFace
  `code-search-net/code_search_net` (parquet) : 4 141 072 lignes / 3,93 Go. Config
  `python` : 412 178 ex. train, ~581 Mo de download.
- **Licence — point d'attention** : chaque exemple vient d'un repo GitHub avec **sa
  propre licence** ; le dataset HF déclare `license: other`. Les licences par repo
  sont fournies dans `{lang}_licenses.pkl` (original). Pour une redistribution clé USB
  propre : **filtrer le sous-ensemble sur les licences permissives** (MIT/Apache/BSD)
  via `_licenses.pkl` — action à intégrer dans la préparation (O5).
- **Alternative légère** : `sentence-transformers/codesearchnet` (1 375 067 lignes,
  492 Mo, colonnes `comment`/`code`) — plus simple, mais même question de licence
  (regroupement par licence non documentée).
- **Représentativité** : paires (docstring, fonction) — parfait pour
  `wiki/pages/patterns/` @dev (error handling, etc.).
- **Coût** : 581 Mo (config python) — téléchargement raisonnable en une fois ;
  embeddings = pré-calcul GPU (O5).

### 2.3 CAIDA Topology — ❌ RESTREINT (jalon de décision Phase 5 réseau)

- **Format** : ITDK (Internet Topology Data Kit), IPv4 Routed /24 Topology Dataset,
  traceroutes Archipelago (Ark).
- **Licence (CAIDA AUA)** : accès **sur formulaire obligatoire** ; licence limitée,
  **non-exclusive, non-transférable, non-assignable, durée 1 an**, usage limité à la
  recherche non-profit/éducation/test interne/gouvernement ; signalement des
  publications ; refus à la discrétion de CAIDA. Données < 1 an : académiques +
  agences US uniquement ; entreprises = programme membre payant.
- **Conséquence** : un subset CAIDA **ne peut pas être redistribué sur la clé USB**
  (licence non transférable) → incompatible avec la distribution JARVIS et avec le
  dépôt git public.
- **Recommandation (à trancher par l'utilisateur — jalon de décision)** : remplacer
  par un dataset réseau **librement redistribuable** :
  - **SNAP AS-Skitter** (Stanford, graphe d'AS, libre) — le plus proche conceptuellement ;
  - **MAWI/WIDE** (trafic réseau, libre avec attribution) ;
  - **ITDK public** (données > 1 an) — mais toujours sous AUA + formulaire → écarté.
  → Ouvre la question : l'ordre O4 (CAIDA 3e) devient « équivalent réseau » selon le choix.

### 2.4 UCI Grid Stability — ✅ GO (Phase 5)

- **Format** : CSV `Data_for_UCI_named.csv`, 10 000 instances, 12 features (τ1-τ4,
  p1-p4, g1-g4) + 2 labels (`stab` continu, `stabf` binaire). `[vérifié par
  téléchargement : 2 397 843 octets ≈ 2,3 Mo, HTTP 200]`.
- **Licence** : CC BY 4.0 (attribution : Arzamasov, Vadim (2018), DOI
  `10.24432/C5PG66`).
- **Représentativité** : simulation de stabilité de réseau électrique 4-nœuds —
  parfait pour `wiki/pages/patterns/grid-stability-indicators.md` @hardware.
- **Conversion** : CSV → JSONL (une instance par ligne, description textuelle des
  features + label).

### 2.5 COCO 2017 — ✅ GO, annotations seules (Phase 5)

- **Format** : annotations JSON (`instances_val2017.json` ≈ 25 Mo, `captions_val2017.json`
  ≈ 18 Mo) ; images 19 Go (train2017.zip) **non nécessaires** : la knowledge base est
  textuelle → on n'ingère que les annotations/captions (aucun stockage d'images).
- **Licence** : CC BY 4.0.
- **Représentativité** : 80 classes objets, 5 000 images val2017 annotées (métadonnées
  + captions) — permet `wiki/pages/concepts/object-detection-patterns.md` @vision
  (le vocabulaire visuel de l'agent est textuel : OCR/détection décrite).
- **Conversion** : JSON annotations → JSONL (par image : catégories présentes,
  captions, taille/bbox résumées).

---

## 3. Plan de préparation JSONL (MT-KB-L0b, après validation)

| Fichier cible (`wiki/sources/`) | Source | Entrées (≤ 1000) | Travail |
|---|---|---|---|
| `mitre-attack.jsonl` | STIX v19.1 (50 Mo) | ~800 techniques | Extraction `attack-pattern` (id/name/description/tactic/detection) |
| `codesearchnet-python.jsonl` | HF config `python` (581 Mo) | 1000 paires licence-permissive | Filtre `_licenses.pkl` + échantillonnage |
| `network-topology.jsonl` | **selon décision utilisateur** (SNAP AS-Skitter ou autre) | 1000 | Selon dataset retenu |
| `grid-stability.jsonl` | CSV UCI (2,3 Mo) | 1000 instances | CSV → JSONL textuel |
| `coco-annotations.jsonl` | `instances_val2017.json` + captions | 1000 exemples | Extraction annotations/captions |

Format commun d'une ligne : `{"id": str, "agent": str, "source": str, "text": str,
"metadata": {...}}` — à figer dans `wiki/SCHEMA.md` (Phase 1) ; la préparation Phase 0
l'utilise tel quel (décision O5 : chunks + embeddings pré-calculés sur GPU externe,
export `.parquet`).

---

## 4. Constats transverses

1. **CAIDA est le seul blocage** : licence non transférable → jalon de décision
   utilisateur (remplacement réseau libre) avant toute préparation.
2. **CodeSearchNet nécessite un filtre licence** : sans lui, la redistribution clé USB
   embarquerait du code sous licence inconnue/non permissive — auditable via
   `_licenses.pkl`.
3. **COCO : zéro image nécessaire** — l'ingestion textuelle des annotations suffit
   (économie de 19 Go).
4. **MITRE et UCI sont prêts pour l'ingest immédiat** (Phase 1 pour MITRE).
5. Toutes les sources vérifiées aujourd'hui sont accessibles sans inscription, sauf
   CAIDA (formulaire).