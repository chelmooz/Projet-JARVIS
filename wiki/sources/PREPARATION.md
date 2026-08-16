# Préparation des sources — MT-KB-L0b

**Date** : 2026-08-17 · **Méthode** : téléchargement réel + conversion (script
temporaire hors repo, exécuté depuis `%TEMP%\opencode\prepare_datasets.py`,
non commité). Format commun des 5 fichiers :

```json
{"id": str, "agent": str, "source": str, "text": str, "metadata": {...}}
```

---

## 1. Fichiers produits (`wiki/sources/`)

| Fichier | Agent | Entrées | Source réelle | Téléchargement |
|---|---|---|---|---|
| `mitre-attack.jsonl` | cyber | **858** (total des techniques v19.1, < 1000) | STIX 2.1 `enterprise-attack-19.1.json`, 53 Mo | `raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-19.1.json` |
| `grid-stability.jsonl` | hardware | **1000** | `Data_for_UCI_named.csv`, 2,3 Mo (10 000 instances) | `archive.ics.uci.edu/static/public/471/data.csv` |
| `network-topology.jsonl` | network | **1000** | `as-skitter.txt.gz`, 33 Mo (1 696 415 nœuds / 11 095 298 arêtes) | `snap.stanford.edu/data/as-skitter.txt.gz` |
| `codesearchnet-python.jsonl` | dev | **1000** | parquet HF config `python` (522 Mo, 412 178 lignes) | `huggingface.co/datasets/code-search-net/code_search_net` → `python/train-00000-of-00001.parquet` |
| `coco-annotations.jsonl` | vision | **1000** | `instances_val2017.json` + `captions_val2017.json` (annotations seules, zéro image) | `images.cocodataset.org/annotations/annotations_trainval2017.zip` (241 Mo) |

## 2. Licences vérifiées

| Source | Licence | Attribution requise |
|---|---|---|
| MITRE ATT&CK v19.1 | MITRE ATT&CK Terms of Use (libre : recherche/dév./commercial) | Oui — « © 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation. » |
| UCI Grid Stability | CC BY 4.0 | Oui — Arzamasov, Vadim (2018), DOI `10.24432/C5PG66` |
| SNAP AS-Skitter | Libre (Stanford SNAP, usage académique/général) | Oui — référence SNAP (Leskovec & Krevl, 2014) |
| CodeSearchNet | **Par dépôt source** (hétérogène) — filtre appliqué, voir §3 | Voir filtre |
| COCO 2017 (annotations) | CC BY 4.0 | Oui — référence COCO (Lin et al., 2014) |

## 3. Filtres appliqués

- **CodeSearchNet — filtre licences permissives** : `python_licenses.pkl` (17 059 repos,
  extrait de `python.zip` — miroir Zenodo, voir §4). Filtre par mots-clés dans le texte de
  licence : `"mit license"` / `"apache license"` / `"bsd"` (heuristique documentée) →
  **9 834 repos permissifs (57,6 %)**. Échantillonnage déterministe : 1000 lignes,
  `random_state=42`, 658 repos distincts dans l'échantillon (tous permissifs).
- **COCO — annotations seules** : aucune image téléchargée (19 Go économisés) ; par image :
  catégories présentes (80 classes) + première légende `captions_val2017.json`.
- **SNAP — topologie textuelle** : degré de chaque nœud (comptage des 11 M arêtes) ;
  les 1000 nœuds de plus haut degré deviennent des entrées décrivant le nœud d'AS.
- **MITRE — extraction `attack-pattern` uniquement** : 858 techniques v19.1 (name,
  description, tactique kill-chain, détection, plateformes), triées par nom.
- **UCI — ligne CSV = une entrée** : 12 features (τ, p, g) + labels `stab`/`stabf` en
  texte et en metadata numérique.

## 4. Déviation documentée (blocage S3 → Zenodo)

- Le bucket S3 d'origine (`s3.amazonaws.com/code-search-net/...`) répond **403 Forbidden**
  (y compris `python.zip` et `python_licenses.pkl` standalone — lien mort côté GitHub,
  confirmé par la discussion HF #3).
- Miroir officiel retenu : **Zenodo record 7857872** (`zenodo.org/record/7857872/files/python.zip`,
  941 Mo) — URL fournie par le staff HF (discussion #3, mise à jour Microsoft CodeXGlue).
  `python_licenses.pkl` extrait de ce zip (données JSONL originales non utilisées : le
  parquet HF suffit).
- COCO : le téléchargement `https://images.cocodataset.org/...` échouait (000) → **http**
  fonctionne (241 Mo, SHA vérifié par extraction zip OK).
- Script de conversion temporaire non commité (conforme aux règles) ; sources brutes
  conservées hors repo dans `%TEMP%\opencode\kb-sources\` (non versionnées).

## 5. Vérifications effectuées

- 5 fichiers JSONL : **0 erreur JSON**, clés `id/agent/source/text` présentes, `id` uniques.
- Comptages : 858 / 1000 / 1000 / 1000 / 1000 lignes (≤ 1000 ✓).
- Échantillons inspectés (MITRE : technique + description ; COCO : catégories + légende).
- Gates repo non applicables (zéro code Python dans le repo modifié).

## 6. Suite

- Phase 1 : figer `wiki/SCHEMA.md` (le format commun ci-dessus devient la référence),
  ingest manuel MITRE ATT&CK (O4), validation Obsidian (O3).
- Pré-calcul embeddings + `.parquet` (O5) sur machine GPU externe depuis ces JSONL.