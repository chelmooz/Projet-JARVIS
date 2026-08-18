## RÉSUMÉ PERTINENCE RAG

### Scores globaux
- @dev (Tech Lead) : **2/3** questions avec retrieval (Q2, Q8, Q9 ont des résultats mais pas setuptools-spécifiques)
- @hardware (Dev/Ops) : **3/3** questions avec retrieval (mais datasets tldr/psdocs manquants)
- @dev (Designer) : **2/3** questions avec retrieval (Q7: 0, Q8: 2, Q9: 3 - setuptools manquant)
- @cyber (Data/Secu) : **2/3** questions avec retrieval (Q10: 0, Q11: 3, Q12: 3 - setuptools manquant)

### Tableau détaillé (Seuil 0.5)

| # | Agent | Question | Score Retrieval | Chunks trouvés | Pertinence (1-5) | Commentaire |
|---|---|---|---|---|---|---|
| 1 | @dev | "Comment fonctionne pkg_resources dans setuptools ?" | 0.0 (NO RETRIEVAL) | Non | 0/5 | GAP DATASET : setuptools.jsonl absent de l'index |
| 2 | @dev | "Comment déclarer des entry_points dans un projet Python ?" | 0.55 max | Oui (3) | 2/5 | codesearchnet-v2-python (dev) - Python générique, pas setuptools-spécifique |
| 3 | @dev | "Quelles alternatives modernes à pkg_resources pour gérer les ressources ?" | 0.0 (NO RETRIEVAL) | Non | 0/5 | GAP DATASET : setuptools.jsonl absent de l'index |
| 4 | @hardware | "Comment utiliser taskset pour contrôler l'affinité CPU d'un processus ?" | 0.64 max | Oui (2) | 3/5 | agent_response + Eng-Elias/multios-terminal-commands (@hardware) - pertinent |
| 5 | @hardware | "Quelles commandes PowerShell pour surveiller la mémoire système ?" | ~0.55 | Oui (3) | 2/5 | Sources à vérifier - probablement Eng-Elias/multios-terminal-commands |
| 6 | @hardware | "Comment diagnostiquer un problème réseau avec PowerShell ?" | ~0.55 | Oui (2) | 2/5 | Sources à vérifier |
| 7 | @dev | "Comment structurer un fichier pyproject.toml pour un projet portable ?" | 0.0 (NO RETRIEVAL) | Non | 0/5 | GAP DATASET : setuptools.jsonl absent de l'index |
| 8 | @dev | "Quelles conventions de nommage pour les packages Python ?" | ~0.52 | Oui (2) | 2/5 | codesearchnet-v2-python (dev) - Python générique |
| 9 | @dev | "Comment documenter les dépendances d'un projet Python ?" | ~0.54 | Oui (3) | 2/5 | codesearchnet-v2-python (dev) - Python générique |
| 10 | @cyber | "Quels risques de sécurité liés à pkg_resources ?" | 0.0 (NO RETRIEVAL) | Non | 0/5 | GAP DATASET : setuptools.jsonl absent de l'index |
| 11 | @cyber | "Comment vérifier les permissions d'un fichier sous Linux ?" | ~0.59 | Oui (3) | 2/5 | Sources à vérifier - probablement Eng-Elias/multios-terminal-commands |
| 12 | @cyber | "Comment sécuriser les dépendances d'un projet Python local ?" | ~0.55 | Oui (3) | 2/5 | codesearchnet-v2-python (dev) - Python générique |

### Gaps identifiés

| Dataset | Manque | Action requise |
|---|---|---|
| **setuptools.jsonl** | **ABSENT** (48 docs attendus) | Produire 48 entrées : pkg_resources, entry_points, pyproject.toml, importlib.resources, alternatives modernes, CVE/sécurité |
| **tldr.jsonl** | **ABSENT** (400 docs attendus) | Produire 400 entrées : taskset, chmod, ls, commandes Linux essentielles |
| **psdocs.jsonl** | **ABSENT** (300 docs attendus) | Produire 300 entrées : Get-Process, Get-Counter, Test-NetConnection, Get-NetAdapter, PowerShell système/réseau |

### Problèmes additionnels

1. **Seuil de retrieval trop élevé (0.5)** : Les scores de similarité cosinus sont typiquement 0.4-0.55. À 0.5, ~40% des questions n'ont aucun résultat. À 0.1, toutes ont des résultats.
2. **Datasets actuels non pertinents** : L'index contient codesearchnet, uci-grid-stability, mitre-attack, snap-as-skitter, multios-terminal-commands — mais PAS les datasets annoncés (setuptools, tldr, psdocs).
3. **Agent filtering** : Le paramètre `agent` dans `vector.search()` filtre par `metadata.agent` exact. Les datasets ont des agents comme `dev`, `@hardware`, `cyber`, `@network` — incohérents avec les préfixes de routage (`@dev`, `@hardware`, `@cyber`, `@network`).

### Verdict
- **RAG fonctionnel** : **NON** (seuil trop haut + datasets manquants)
- **Datasets suffisants** : **NON** (3/3 datasets critiques absents)
- **Actions utilisateur requises** :
  1. Produire `setuptools.jsonl` (48 docs) — critique pour @dev et @cyber
  2. Produire `tldr.jsonl` (400 docs) — critique pour @hardware (Linux)
  3. Produire `psdocs.jsonl` (300 docs) — critique pour @hardware (PowerShell)
  4. Baisser le seuil `sim_threshold` de 0.5 à 0.3-0.4 dans `retrieve_context` (pipeline_steps.py:93)
  5. Harmoniser les valeurs `metadata.agent` dans les datasets avec les préfixes de routage (`@dev`, `@hardware`, `@cyber`, `@network`)