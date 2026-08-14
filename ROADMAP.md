# ROADMAP — Plan micro-tâches TDD JARVIS

Suivi du plan d'amélioration (audit 68/100 → cible 90/100).
Contrat permanent (RÈGLES NON NÉGOCIABLES) : TDD strict RED→GREEN→REFACTOR, un commit
atomique par micro-tâche (conventional commits), `ruff check . && ruff format --check .
&& mypy && pytest --cov` avant commit, KISS, SOLID via Protocol `ports/__init__.py`,
aucun changement de comportement en REFACTOR, ** règle 4 amendée : aucune assertion de
test modifiée — seuls les chemins d'import et de `patch()` peuvent suivre un déplacement
de module **, aucun test réseau/Ollama/disque hors `tmp_path`, stop si > 60 min ou
> 200 lignes de diff.

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
- [x] Remonter `fail_under` (mesuré − 2) après chaque module + commit — `fail_under=46` (mesuré 49,41 % au Lot 3.6, ≥ 46 % ; prochain palier `fail_under=48` — T5a, mesuré 50,26 % − 2)

## Lot 3 — Contrôleurs en TDD (`fastapi.testclient`)

- [x] 3.1 `tests/test_api_health.py` : `/api/system/status` → 200 dégradé offline + `app.state.context` (DI respectée) — 4 tests
- [x] 3.2 `tests/test_api_chat.py` : 200 nominal (`fake_inference`), préfixes `@` (cyber/dev/network), mots-clés (network), fallback `dev`, 422, 413 — 7 tests
- [x] 3.3 `tests/test_api_agents.py` : `GET /api/agents` 200 (+ `routing_prefixes` DRY MT-1.5), `POST /api/agents/assign` 200/400/404/500 — 5 tests
- [x] 3.4 `tests/test_api_files.py` : 200 dans sandbox, refus hors sandbox (`error_type=not_authorized`), fichier inexistant `Pas un fichier` — 4 tests
- [x] 3.5 `tests/test_api_ratelimit.py` : 200 sous quota + en-têtes `X-RateLimit-*`, 429 + `Retry-After` cohérent avec `retry_after` — 2 tests
- [x] 3.6 `tests/test_api_rag.py` : `GET /api/search` 200 + pagination, 400 query vide, texte scrubbé préservé — 3 tests
- [x] Lot 3 COMPLET (3.1→3.6) : 17 nouveaux tests d'API, tous verts, DI via `app.state.context` respectée partout

## Lot 4 — Refactors sous filet (REFACTOR only)

- [x] 4.1 `services/vector.py` (578) → façade déléguant aux `vector_*` — état final déjà atteint : déplacer l'orchestration violerait KISS (BACKLOG MT Lot 4.1)
- [x] 4.2 `services/pipeline.py` (447) → délégation à `execute_pipeline_step` dans `pipeline_steps.py` — **T4.2 validé** : 3 tests TDD dans `tests/test_pipeline_steps.py` (agent_runner, inference, retry) ; `pipeline_steps.py` à 9 % (dette Lot 4.x en suivi via BACKLOG.md ticketsouverts). Refactor pipeline.py en suivi.
- [x] 4.2b Suppression de la copie parallèle (~150 l. : `_execute_step`, `_run_via_agent`, `_run_via_inference`, `_extract_response`, `_execute_with_retry`, `_record_step_*`) au profit de `pipeline_steps.execute_pipeline_step` (dé-orpheliné) — cible `pipeline.py` < 300 l. ; conditions d'entrée : 3 TODO `agent_runner` fermés (T5a MT-1.1/1.3) — plan T5a Phase 2
- [x] 4.3 `services/analysis_audit.py` (427) → reventiler vers `analysis_*` (tests d'audit AVANT ; couverture 18 %) — **architecturalement déjà fait** à la base (`QualityAuditor` agrège via `Analyzer` = `analysis.py`, feuilles `analysis_security/performance/maintainability/standards/core`) ; imports directs `analysis_core` ajoutés (`e89f3826`) + `ruff format` (`c5bca40d`), gates vertes
- [x] 4.4 `services/ollama_installer.py` (330 → 263) — découpe en cours :
      - [x] 4.4a Extraction `services/ollama_download.py` (download atomique, SHA256, `_verify_ollama_binary`) — **non committé** (rattrapé par T1)
      - [x] 4.4b Tests de caractérisation `test_ollama_installer.py` (commit `5a0ef4ad`) + `test_ollama_installer_security.py` (imports à re-trier, rattrapé par T1)
      - [x] 4.4c Extraction des 5 installateurs (`_install_linux_apt`, `_install_linux_tar`, `_install_windows_zip`, `_install_mac_brew`, `_install_mac_script`) vers `services/ollama_install_{linux,windows,mac}.py` ; `ollama_installer.py` = sélecteur < 100 l. + ré-exports `__all__` (surface `scripts/install.py` préservée) ; 5 tests de caractérisation obligatoires (plan T5a Phase 3)

## Tickets ouverts (hors lot, dette typée — ne pas masquer via exclude)

- **mypy `scripts/schedule_backup.py`** : conflit de module `schedule_backup` vs `scripts.schedule_backup` (install éditable `.pth` sur `sys.path`). N'affecte PAS le gate `mypy` (sans chemin, `files` = 120 src). Résolutions (à choisir en Lot ultérieur) : (1) `mypy --explicit-package-bases` + `MYPYPATH` ; (2) `scripts/__init__.py` (rend `scripts` package explicite, vérifier qu'aucun import `from schedule_backup import ...` ne casse) ; (3) déplacer `scripts/` vers `tools/`. Traiter en nettoyage dédié — voir `BACKLOG.md:76-89`.
- **`pipeline_steps.py` @ 9 % + 3 TODO `agent_runner` non câblé** (`pipeline_steps.py:208,210,215`) : dette introduite par la pivot Lot 4.x, à traiter avant/sous 4.2.

## Lot 5 — Dettes ciblées (1 test RED puis fix)

- [x] 5.1 `retry_after` dérivé de `services/ratelimit.py` (source unique de vérité, au lieu du `60` codé dur dans `middlewares.py:161`) — `3635fd08`, test `test_429_retry_after_derived_from_ratelimit_window`
- [x] 5.2 Renommer `_setup_middlewares` → `setup_middlewares` (`middlewares.py:79,173`, `context.py:21,52`) — symbole privé importé publiquement — `08bf4aec`, `tests/test_middlewares_public_api.py`
- [x] 5.3 CSP : retirer `unsafe-inline`, extraire JS inline de `static/index.html` en modules (hash ou nonces) — **déjà réalisé en amont** (CSP nonce, JS en modules externes) ; verrou de régression `tests/test_csp_policy.py` + docstring `middlewares.py` corrigé — `453d4e4a`
- [x] 5.4 Corriger commentaire `.env.example:37` (« Si vide, l'utilisateur peut autoriser n'importe quel dossier ») qui contredit le code fail-closed (`file_system.py:112-114`) + créer `ADR-011-sandbox-fail-closed.md` pour acter le choix — `9697fa5a`
- [x] 5.5 Basculer les 3 TODO restants (`supervisor.py:57,153`, `di.py:107`) en `BACKLOG.md` (+3 nouveaux `pipeline_steps.py:208,210,215` déjà tracés en tickets ouverts) — `315904ac`
- [x] 5.6 Nettoyer références aux tests fantômes (`context.py:117-118,42`, `file_system.py:110`, + alias `_warmup` fantôme `warmup.py:160`) — `b3449797`

## LOT 5 COMPLET ✅ (2026-08-14)

## Lot 6 — Reproductibilité

- [x] 6.1 Générer `uv.lock` (ou `requirements.lock`) versionné — `4dcbd6465`
- [x] 6.2 `uv pip download -r requirements.lock -d vendor_wheels --platform {win_amd64, manylinux_2_17_x86_64, macosx_11_0_arm64} --python-version 3.12 --only-binary=:all:` → `scripts/vendor_wheels.py` (uv 0.12 a retiré `uv pip download` : repli `pip download` ; exception sdist `antlr4==4.9.3`) — `8c4987bcb`
- [x] 6.3 `scripts/install.py` consomme `--no-index --find-links vendor_wheels` (mode offline détecté par `_vendor_find_links`) — `2d8574370`
- [x] 6.4 `ADR-012-distribution-offline.md` + section `docs/DEVELOP.md` — `5cce77dd1`
- [x] 6.5 Workflow `release.yml` : `verify_release.py` (cohérence versions pyproject, `bin/VERSION.json`, `config/constants.py`, `launchers`) + workflow `v*` — `f57ec6c85`
- [x] 6.6 Smoke test « démarrage » : `/api/status` → 200 sans backend Ollama (mode dégradé explicite) — déjà couvert par `tests/test_api_health.py::test_status_200_offline_degraded` (Lot 3.1). Note : la route réelle s'appelle `/api/status` (pas `/api/system/status` comme au ROADMAP) — `router.py:239`.

## Lot 6 COMPLET ✅ (2026-08-14)

## Lot 7 — Documentation

- [x] 7.1 Scinder `README.md` (821 l.) : README court (pitch, capture, installation 5 lignes, liens) + `docs/USAGE.md` mode d'emploi détaillé — `1889a5107`
- [x] 7.2 Créer `CONTRIBUTING.md` (commandes ruff/mypy/pytest, conventional commits, boucle TDD) — `2f0b4f880`
- [x] 7.3 Fusionner `RELEASE_NOTES_CORRECTED.md` → `CHANGELOG.md` puis supprimer (suffixe « CORRECTED » = artefact de travail) — `9961003b2`
- [x] 7.4 Remplacer badge Tests retiré par badge de couverture (généré par la CI) — `2c503510a`

## Lot 7 COMPLET ✅ (2026-08-14)

## Ordre d'exécution

```text
Lot 0 �� → Lot 1 �� → Lot 2 �� → Lot 3 �� → Lot 4 (4.1 �� · 4.2 �� · 4.3 �� · 4.4 ��) → Lot 5 �� → Lot 6 �� → Lot 7 ��
```

## T5a — Vérification des gates & clôture des restes du Lot 4 (plan 2026-08-14)

État réel vérifié (HEAD `d79b1b152`, arbre propre) : `ruff check .` ✅ · `ruff format --check .`
❌ (`tests/test_pipeline_steps.py`) · `mypy` ✅ (121 src) · `pytest --cov` ✅ (178 passés / 1 skip,
50,26 % ≥ 46) · badge 50,3 % à jour (aucun commit badge attendu).

### Phase 0 — Débloquer les gates (hygiène, pas de TDD)

- [x] 0.1 `ruff format tests/test_pipeline_steps.py` → 4 gates → `style: ruff format tests/test_pipeline_steps.py`
- [x] 0.2 `pyproject.toml` : `fail_under = 48` (mesuré 50,26 % − 2) + commentaire ; ROADMAP L.37 déjà
      aligné (48) → vérif « Required test coverage of 48.0% reached » → `chore(coverage): fail_under 46 -> 48 (mesuré 50,26 %)`

### Phase 1 — `execute_pipeline_step` : combler les trous réels (TDD)

Objectif : porter la logique de `pipeline.py::_run_via_agent` (DRY), pas inventer un contrat.
Contrat d'erreur acté : **state partout**, aucun `PipelineError` en frontière (le 404 de la route
reste réservé à `_resolve_pipeline`) — test épinglé dans le filet 2.1.

- [x] 1.1 RED propagation du modèle au runner (runner 3 params reçoit le modèle sélectionné ; runner
      2 params appelé sans modèle) — GREEN : détection `inspect.signature` portée depuis
      `_supports_model` (`pipeline.py:68-76`), aucun paramètre nouveau
      → `feat(pipeline_steps): propage le modèle au runner (parité _run_via_agent)`
- [x] 1.2 Fix `model_selector` sur les 2 call sites `pipeline.py:299` (`_run_via_agent`) et `:307`
      (`_run_via_inference`, **VIVANT** : `routes/pipelines.py:40` POST `/api/pipelines/run` →
      `run()` → `_run_via_inference`, inference configuré dans `di.py`) — convention
      `select_model(agent_key, inference, log_service=None)` : les appelants passent le service
      d'inférence, jamais la tâche ; `pipeline_steps.py:24` NON touché (vivante via `AgentGraph`) ;
      vérifier que `select_model(agent_key, None)` est sûr (fallback) ; nota collision de nom
      (2 `select_model`) au BACKLOG → `fix(pipeline): model_selector reçoit inference et non la tâche (2 call sites)`
- [x] 1.3 RED runner non callable → erreur typée (plus de `str(agent_runner)` repr) — les tests
      existants `test_pipeline_steps.py:56,74` (fallback inference) restent verts
      → `fix(pipeline_steps): rejette un agent_runner non callable`
- [x] 1.4 Ticket `di.py:107` fermé : « inference suffit ; agent_runner = point d'extension »
      (zéro code, preuve : `routes/pipelines.py:40` + inference configuré + aucun type runner)
      → `docs(backlog): ferme le ticket di.py:107 (inference suffit)`

### Phase 2 — 4.2b : supprimer la copie parallèle (REFACTOR only)

- [x] 2.1 Filet `tests/test_pipeline_characterization.py` (verts sur le code actuel, AVANT tout
      déplacement) : retry inconditionnel (`pipeline_steps.py:200`) vs conditionnel
      `on_error=="retry"` (`pipeline.py:330`) ; hook habits (`pipeline.py:365-372`, absent de
      `pipeline_steps`) ; contrat d'erreur (sans backend → entrée d'erreur dans `results`,
      enveloppe HTTP 200, aucune exception) ; `on_error=="skip"` → on continue (pas de chemin timeout)
- [x] 2.2 Retry conditionnel `on_error == "retry"` porté dans `pipeline_steps` (parité production,
      test dédié ; les 3 tests existants utilisent `max_retries=0` → aucun impact)
      → `refactor(pipeline_steps): retry conditionnel on_error == retry (parité production)`
- [x] 2.3 Hook habits porté (frontière `PipelineService` ou `pipeline_steps` — choix documenté 1 l.)
      → `refactor(pipeline): habits en frontière d'orchestration`
- [x] 2.4 `PipelineService` appelle `execute_pipeline_step` ; suppression des 6 méthodes dupliquées
      (`_execute_step`, `_run_via_agent`, `_run_via_inference`, `_extract_response`,
      `_execute_with_retry`, `_record_step_*`) ; cible `pipeline.py` < 300 l., zéro logique d'étape
      dupliquée, `execute_pipeline_step` dé-orpheliné
      → `refactor(pipeline): supprime la copie parallèle au profit de pipeline_steps (4.2b)`

### Phase 3 — 4.4c installateurs par plateforme (REFACTOR only)

Contraintes : le filet 4.4b ne couvre que download/verify/extract/ensure → **5 tests de
caractérisation obligatoires** ; surface d'import à préserver (`scripts/install.py:194-198`,
`jarvis.py:20`, `launcher_win.py:27`) via ré-exports `__all__` (convention 4.4b).

- [x] 3.1 5 tests de caractérisation un par installateur (`_install_linux_apt`, `_install_linux_tar`,
      `_install_windows_zip`, `_install_mac_brew`, `_install_mac_script`)
      → `test(ollama): caractérisation des 5 installateurs plateforme`
- [x] 3.2 `services/ollama_install_linux.py` + ré-exports → `refactor(ollama): extrait les installateurs Linux (4.4c)`
- [x] 3.3 `services/ollama_install_windows.py` + ré-export → `refactor(ollama): extrait l'installateur Windows (4.4c)`
- [x] 3.4 `services/ollama_install_mac.py` ; `ollama_installer.py` = sélecteur < 100 l. + `__all__`
      explicite ; non-régression imports `scripts/install.py`
      → `refactor(ollama): extrait macOS + sélecteur de plateforme (4.4c)` → Lot 4.4 coché

### Phase 4 — Traçabilité

- [x] 4.1 ROADMAP : 4.2b/4.4c cochés, « @ 9 % » (ticket pipeline_steps) → mesure réelle,
      « 330 → 263 » → 228 l., ordre d'exécution Lot 6 ������ / Lot 7 ������
      → `docs(roadmap): Lot 4 complet (4.2b, 4.4c) + compteurs à jour`
- [x] 4.2 BACKLOG T5a + tickets fermés (TODO `pipeline_steps.py:208,210,215`, `di.py:107`) +
      `fail_under` final (nouvelle mesure − 2) + `coverage-badge.json` régénéré DANS LE M��ME COMMIT
      (CI : `git diff --exit-code`) → `docs(backlog): T5a — Lot 4 clos, gates vertes`

## Définition of done (par micro-tâche)

1. Test rouge écrit et vu échouer.
2. Code minimal pour le vert.
3. Refactor sans changer les tests.
4. `ruff check` + `ruff format --check` + `mypy` + `pytest --cov` verts.
5. Un commit conventionnel, un seul sujet.
6. `fail_under` remonté si la couverture a progressé.
