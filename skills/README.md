# Skills découverts (dépôt)

Ce dossier est le **dépôt des skills découverts/générés** de JARVIS, par opposition à :

- `config/skills.json` — skills *built-in* déclaratifs (source de vérité du backend),
- `.opencode/skills/` — skills de l'assistant de développement (outil tiers, ignoré par JARVIS).

## Rôle futur (vectorisation → skills activables)

Lorsque la vectorisation des runbooks (`scripts/ingest_runbook.py`, `services/vector.py`)
sera étendue à la **découverte de skills**, chaque runbook (ou section) porteur d'une
métadonnée `skill` (ex. frontmatter `id` / `name` / `description` / `category`) sera
référencé ici sous la forme `skills/<nom>/skill.md`.

Ces skills découverts deviennent alors :

- **indexés par embedding** (recherche sémantique via `VectorService`),
- **activables/désactivables** depuis l'onglet **Skills** de l'interface web (le toggle
  persiste l'état `enabled` dans `config/skills.json`),
- **injectés dans le contexte des discussions** quand ils sont activés (voir
  `GET /api/skills/context` câblé dans `controllers/context.py`).

## Pourquoi un dossier dédié (et non `config/skills.json` seul)

`config/skills.json` reste la source de vérité des skills *déclarés*. Ce dossier accueille
le **contenu vectorisable** des skills issus des runbooks, séparé pour ne pas mélanger
métadonnées et corpus documentaire. Une seule source de vérité par type : déclaratif vs
contenu indexé.

## État actuel

Ce dossier est **vide en attend** (le précédent `tree.txt` d'inventaire a été supprimé).
Il ne doit pas rester un résidu : son rôle est documenté ici et il se peuplera
automatiquement lors de la découverte de skills par vectorisation.
