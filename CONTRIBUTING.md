# Contribuer à JARVIS Portable Edition

Merci de vouloir contribuer ! Ce dépôt est un terrain d'apprentissage et
d'expérimentation : la qualité du code et des tests prime sur la quantité.

## Boucle TDD (obligatoire)

Toute modification de code suit la boucle **rouge → vert → refactor** :

1. **Rouge** — écrire un test qui échoue (qui décrit le comportement attendu).
2. **Vert** — code minimal pour faire passer le test.
3. **Refactor** — nettoyer sans changer les tests (un commit par sujet).

Règle stricte : aucune assertion de test existante n'est modifiée pour faire
passer un test — seuls les chemins d'import et les `patch()` peuvent suivre un
déplacement de module.

## Commandes de validation

À exécuter **avant chaque commit** :

```bash
ruff check .                # lint strict (line length 120)
ruff format --check .       # formatage
mypy                        # types stricts
pytest --cov                # tests + couverture (fail_under dans pyproject.toml)
```

Le frontend a ses propres tests (vitest/jsdom) :

```bash
cd static && npm install && npx vitest run
```

## Conventional commits

Chaque commit est atomique et suit `type(scope): sujet` :

| Type | Usage |
|------|-------|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `refactor` | Remaniement sans changement de comportement |
| `test` | Ajout/modification de tests |
| `docs` | Documentation |
| `chore` | Ménage (TODO, imports morts, caches) |
| `build` / `ci` | Dépendances / workflows |

Exemples : `fix(ollama): vérifie le SHA256 avant extraction` ·
`test(ratelimit): retry_after dérivé de WINDOW` · `docs(roadmap): Lot 5 coché`.

## Conventions de code

- **Architecture MVC + Ports** — la composition root est dans `jarvis.py` et
  `controllers/router.py` ; les services parlent à des Protocols (`ports/`).
- **Clean code / KISS** — fonctions courtes, une seule responsabilité, pas de
  sur-ingénierie, pas de code mort.
- **Types stricts** — mypy vert sur `services/`, `controllers/`, `agents/`,
  `graph/`, `ports/`, `config/`, `models/`.
- **Single source of truth** — la version vit dans `config/constants.py`
  (cohérence vérifiée par `scripts/verify_release.py`).
- **Dépendances** — épinglées dans `uv.lock` / `requirements.lock`
  (voir `docs/DEVELOP.md`, section Reproductibilité).

## Documentation

- Décision d'architecture → ADR dans `docs/adr/` (ADRx-xxx-sujet.md, structure
  Contexte / Décision / Conséquences).
- Guide développeur → `docs/DEVELOP.md` ; mode d'emploi utilisateur →
  `docs/USAGE.md`.
- Le journal de session et les décisions de chantier sont tracés dans
  `BACKLOG.md` (mis à jour après chaque micro-tâche).

## Processus

1. Petites micro-tâches, une seule action à la fois.
2. Tests d'abord (TDD), gates vertes avant commit.
3. Un commit conventionnel par sujet.
4. Couverture : `fail_under` remonté dès que la couverture progresse.
5. Push seulement quand demandé — le dépôt reste local par défaut.
