# ROADMAP — Plan micro-tâches TDD JARVIS

Suivi du plan d'amélioration (audit 68/100 → cible 90/100).
Contrat permanent (RÈGLES NON NÉGOCIABLES) : TDD strict RED→GREEN→REFACTOR, un commit
atomique par micro-tâche (conventional commits), `ruff check . && ruff format --check .
&& mypy && pytest --cov` avant commit, KISS, SOLID via Protocol `ports/__init__.py`,
aucun changement de comportement en REFACTOR, aucun test réseau/Ollama/disque hors
`tmp_path`, stop si > 60 min ou > 200 lignes de diff.

## Lot 0 — Verrou d'outillage (~1 h)

- [x] 0.1 Ajouter `mypy>=1.13` à `[project.optional-dependencies].dev` (`pyproject.toml`)
- [x] 0.2 Retirer `exclude = [".github/workflows"]` de `[tool.ruff]`
- [x] 0.3 `fail_under = 60` → `fail_under = 0` + supprimer le commentaire « Mesure réelle 62.95 % »
- [x] 0.4 Créer `.github/workflows/ci.yml` (push+PR, matrice 3.12/3.13, cache pip, ruff/mypy/pytest)
- [x] 0.5 Retirer le badge `Tests-478` de `README.md:9`
- [x] 0.6 `ruff format` sur 4 fichiers préexistants non formatés (router, jarvis, ollama_adapter, vision)
- [x] 0.7 Corrections `mypy` : typage générateur SSE (`system.py`), `cast` vision (`vision.py`), override `rapidocr`

## Lot 1 — Socle de test (~1 h)

- [x] 1.1 `tests/conftest.py` : fixture `sandbox_root` (pose `JARVIS_FILES_SANDBOX_ROOT` sur `tmp_path`) + smoke test
- [x] 1.2 conftest : `fake_inference` implémentant `ChatPort` (réponses déterministes) + fixture `inference`
- [x] 1.3 conftest : `fake_vector` (`VectorPort`) + `fake_embedding` (`EmbeddingPort`) en mémoire + fixtures

## Lot 2 — Noyau critique en TDD (cible ≥ 85 %)

- [x] 2.1 `services/sanitize.py` (car. non imprimables, troncature, modèle invalide, base64, scrub email/IP/token) — 96 %
- [x] 2.2 `services/file_system.py` (`..`, absolu, symlink sortant, casse Windows, racine absente→`FileSystemError`, valide) — 87 %
- [x] 2.3 `services/score.py` (bornes 0/1, vide, négatif) — 100 %
- [x] 2.4 `services/chunker.py` (< taille, = taille, overlap, vide, unicode multi-octets) — 98 %
- [x] 2.5 `services/vector_weighting.py` + `vector_dimension.py` (pondérations déterministes, dimension incohérente rejetée) — 99 %/100 %
- [x] 2.6 `services/router.py` (routage mot-clé, défaut, ambigu) — 100 % (+fix bug `.task`)
- [x] 2.7 `services/selector.py` (profil YAML, profil manquant, fallback) — 98 %
- [ ] Remonter `fail_under` (mesuré − 2) après chaque module + commit

## Lot 3 — Contrôleurs en TDD (`fastapi.testclient`)

- [ ] 3.1 `tests/test_api_health.py` : `/api/system/status` → 200 sans Ollama (dégradé explicite)
- [ ] 3.2 `tests/test_api_chat.py` : 200 nominal (`fake_inference`), 422, 413
- [ ] 3.3 `tests/test_api_files.py` : 200 dans sandbox, 403/400 hors, 404
- [ ] 3.4 `tests/test_api_ratelimit.py` : 429 + en-tête `retry_after` cohérent
- [ ] 3.5 `tests/test_api_vector.py` : recherche avec `fake_vector`

## Lot 4 — Refactors sous filet (REFACTOR only)

- [ ] 4.1 `services/vector.py` (578) → façade déléguant aux `vector_*` (API identique, tests 2.5+3.5 verts)
- [ ] 4.2 `services/pipeline.py` (447) → exécution d'étape dans `pipeline_steps.py` (1 test intég/pipeline AVANT)
- [ ] 4.3 `services/analysis_audit.py` (427) → reventiler vers `analysis_*` (tests d'audit AVANT)
- [ ] 4.4 `services/ollama_installer.py` (330) → download+hash / install / détection version (`test_ollama_installer_security.py` intact)

## Lot 5 — Dettes ciblées (1 test RED puis fix)

- [ ] 5.1 `retry_after` dérivé de `services/ratelimit.py` (source unique)
- [ ] 5.2 Renommer `_setup_middlewares` → `setup_middlewares` (`middlewares.py:79,173`, `context.py:21,52`)
- [ ] 5.3 CSP : retirer `unsafe-inline`, extraire JS inline de `static/index.html` en modules
- [ ] 5.4 Corriger commentaire `.env.example:37` + `ADR-011-sandbox-fail-closed.md`
- [ ] 5.5 Basculer les 3 TODO (`supervisor.py:57,153`, `di.py:107`) en `BACKLOG.md`
- [ ] 5.6 Nettoyer références aux tests fantômes (`context.py:117`, `file_system.py:110`)

## Lot 6 — Reproductibilité

- [ ] 6.1 Générer `uv.lock` (ou `requirements.lock`) versionné
- [ ] 6.2 `uv pip download -r requirements.lock -d vendor_wheels --platform {win_amd64, manylinux_2_17_x86_64, macosx_11_0_arm64} --python-version 3.12 --only-binary=:all:`
- [ ] 6.3 `scripts/install.py` + `install_portable_python.py` consomment `--no-index --find-links vendor_wheels`
- [ ] 6.4 `ADR-012-distribution-offline.md` + section `docs/DEVELOP.md`
- [ ] 6.5 Workflow `release.yml` : `verify_release.py` + cohérence versions (pyproject, VERSION.json, constants, launchers)

## Lot 7 — Documentation

- [ ] 7.1 Scinder `README.md` (821 l.) : README court + `docs/USAGE.md`
- [ ] 7.2 Créer `CONTRIBUTING.md` (ruff/mypy/pytest, conventional commits, boucle TDD)
- [ ] 7.3 Fusionner `RELEASE_NOTES_CORRECTED.md` → `CHANGELOG.md` puis supprimer
- [ ] 7.4 Remplacer badge Tests retiré par badge de couverture (CI)

## Ordre d'exécution

```text
Lot 0 → Lot 1 → Lot 2 → Lot 3 → Lot 4 → Lot 5 → Lot 6 → Lot 7
```

## Définition of done (par micro-tâche)

1. Test rouge écrit et vu échouer.
2. Code minimal pour le vert.
3. Refactor sans changer les tests.
4. `ruff check` + `ruff format --check` + `mypy` + `pytest --cov` verts.
5. Un commit conventionnel, un seul sujet.
6. `fail_under` remonté si la couverture a progressé.
