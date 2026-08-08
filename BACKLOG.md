# 📋 BACKLOG.md — Plan de Micro-Tâches TDD (audit du 25/07/2026)

---

## 🔧 C1 — Retrait du consentement diagnostic (usage mono-utilisateur, clé USB) — 08/08/2026

> Décision Michel : « je n'ai pas besoin de consentement, donne tous les droits,
> ce n'est pas un inconnu qui possède la clé ». Le gate `.diagnostic_consent`
> (AUDIT.1 : mécanisme décoratif par design, contournable en 1 ligne) est retiré :
> exécution directe des outils externes (witr, psinfo, ...) sans fichier ni toggle.
> KISS : suppression pure, pas de config pour réactiver (YAGNI).

| # | Micro-tâche | Statut |
|---|-------------|--------|
| C1.1 | **RED** : `test_diagnostic_ext_charact.py` — `test_run_sans_consentement_court_circuite` remplacé par `test_run_sans_consentement_execute` : `CommandExecutor.run("smartctl")` (sans arg consent) doit exécuter (subprocess appelé) → échoue : TypeError param manquant | ✅ |
| C1.2 | **GREEN** : `executor.py` — supprime le paramètre `consent_given` de `run()` + le court-circuit « Consentement non donné » | ✅ |
| C1.3 | **RED** : `test_diagnostic_ext.py` — `test_run_tool_without_consent` remplacé : `_run_tool("smartctl")` sans consent → erreur « introuvable » (pas « Consentement ») ; `test_is_ready_false_without_consent` remplacé par `test_is_ready_sans_consentement_selon_outils` | ✅ |
| C1.4 | **GREEN** : `service.py` — supprime `ensure_consent`/`grant_consent`/`revoke_consent`/`_consent_given`/param `consent_file` ; `is_ready()` ne dépend plus du consentement ; `_run_tool` n'appelle plus `run(consent_given=...)` | ✅ |
| C1.5 | **RED** : `test_api.py::TestDiagnosticConsent` réécrit — `GET /api/diagnostic/consent` → `{"consent_given": true}` (toujours) ; `POST` → 200 sans écriture fichier | ✅ |
| C1.6 | **GREEN** : `controllers/routes/diagnostic_ext.py` — GET renvoie `{"consent_given": true}` constant, POST no-op (compat) ; `ConsentRequest` **conservé** dans `models/schemas.py` (validé par le POST : body `{}` → 422, contrat préservé) | ✅ |
| C1.7 | **RED** : `test_consent_ui_removed.py` (pattern test_dark_mode) — index.html sans `#s-diagnostic-consent` ni `#consent-status` ; app.js sans `restoreConsentState`/`setConsentStatus` → échoue (2 tests) | ✅ |
| C1.8 | **GREEN** : `static/index.html` (groupe « Diagnostic externe » supprimé) + `static/assets/js/app.js` (bloc consentement + appel boot `restoreConsentState()` supprimés) + `style.css` (`.consent-status`/`.consent-ok`/`.consent-warn` supprimés) | ✅ |
| C1.9 | **VERIFY** : périmètre C1 → **129 passed** (diagnostic_ext ×2 + toolbox 21 + api 44 + consent_ui 2 + config 60) ; ruff 0 erreur ; suite complète **921 passed, 14 failed / 6 errors hors périmètre** (pré-existants : intégration Ollama/405, vectorize, system, install_final_message) | ✅ |
| C1.10 | **Docs** : README (prérequis consentement → note « aucun consentement requis ») ; `docs/inventory-dead-code.md` (ligne consent supprimée) ; BACKLOG preuves ci-dessous | ✅ |

**Preuve C1** :
```
pytest tests/test_diagnostic_ext.py + charact + toolbox + api + consent_ui + config_files → 129 passed
pytest tests/ → 921 passed / 14 failed + 6 errors hors périmètre (pré-existants)
ruff check services/diagnostic_ext controllers/routes/diagnostic_ext.py ... → All checks passed!
```

**Leçons apprises (C1)** :
- `is_ready()` dépend de `sha256_ok` : un test « outil dispo » doit fournir le **hash
  réel** du binaire factice (`hashlib.sha256(content).hexdigest().upper()`), pas `sha256: ""`
  (liste vide → jamais prêt).
- `ConsentRequest` est **conservé** dans les schémas même si le consentement est retiré :
  le POST no-op s'en sert pour valider le body (422 sur body vide) — suppression = 1 API break.
- L'API de consentement reste en place **en no-op** (retourne toujours `true`) au lieu d'être
  supprimée : compat clients/frontend anciens, 2 lignes de code (KISS).
- Les 14 échecs de la suite complète sont **pré-existants** (intégration Ollama sans serveur,
  `test_system`/`vectorize`/`install_final_message` liés à l'état du workspace — hors périmètre C1).

**Prochaine micro-tâche** : aucune — C1 clos.

---

## 🔧 W1 — witr : requêtes port via `--port` (bug P1 de l'audit binaire) — 06/08/2026

> P1 vérifié binaire en main : `witr --json 8000` traite « 8000 » comme un **nom**
> (substring) → *no process found* (exit 2). Bon appel : `witr --json --port 8000`.
> `run_witr` passait tout target en positionnel `{target}` — les ports (promis par
> le prompt agent T10) étaient cassés en production.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| W1.1 | **RED** : `test_cle_port_utilise_port_args_witr` (TestBuildArgs — cfg witr `port_args`, kwargs `{"port": "8080"}` → `["--json", "--port", "8080"]`) → échoue (template port_args ignoré) ; `test_run_witr_passe_le_target_port` mis à jour (contrat cible : target numérique → clé `port`) → échoue (passait `{"target": "8080"}`) | ✅ |
| W1.2 | **GREEN** : `executor.py::build_args` — si `"port" in extra_kwargs` → template `port_args` (indépendant plateforme, repli `args`) sinon template plateforme existant ; `service.py::run_witr` — `target.isdigit()` → `{"port": target}`, sinon `{"target": target}` ; `config/diagnostic_tools.yaml` — witr `port_args: ["--json", "--port", "{port}"]` + `allowed_params: [target, port]` | ✅ |
| W1.3 | **VERIFY** : `pytest test_diagnostic_ext_charact + test_diagnostic_ext + test_toolbox` → **81 passed** ; `test_config_files` → 44 passed ; ruff 0 erreur | ✅ |
| W1.4 | **E2E réel** : consentement temporaire + binaire réel — `run_witr("47001")` → `data.Target.Type="port"`, `Target.Value="47001"`, `Process.Command="System"`, ancestry 1 (avant W1 : « no process found matching ») ; régression nom : `run_witr("explorer")` → `success: True` inchangé ; fichier consentement nettoyé | ✅ |

**Preuve W1** :
```
pytest tests/test_diagnostic_ext_charact.py tests/test_diagnostic_ext.py tests/test_toolbox.py → 81 passed
pytest tests/test_config_files.py tests/test_diagnostic_ext_charact.py → 44 passed
ruff check executor.py service.py test_diagnostic_ext_charact.py → All checks passed!
E2E: run_witr('47001') → {'target_type': 'port', 'target_val': '47001', 'proc': 'System', 'ancestry_n': 1, 'returncode': 1}
E2E: run_witr('explorer') → {'success': True, 'target_type': 'name', 'proc': 'Explorer.EXE'}
```

**Leçons apprises (W1)** :
- Le contrat de `build_args` évolue : le choix du template dépend désormais de la **clé** présente dans `extra_kwargs` (port vs nom), pas seulement de la plateforme. `port_args` est volontairement unique (flags witr identiques sur win32/linux/darwin) — pas de duplication linux_port_args/darwin_port_args (YAGNI).
- `target.isdigit()` est délibérément simple : un target numérique = port. Le cas « PID » reste non traité (prompt T10 : demander PID ou port — un numéro nu sera résolu en port ; acceptable, witr renvoie alors proprement « not found »).
- **P3 confirmé en E2E** : `run_witr('47001')` → exit 1 (warnings witr, ex: *listening on public interface*) → `success: False` malgré une ancestry complète. À traiter en micro-tâche séparée (W3 proposée).

**Prochaine micro-tâche** : W2 (not-found → erreur « cible introuvable » au lieu de « Sortie JSON invalide ») ou W3 (exit 1 = succès avec warnings).

---

## 🔧 W2 — Not-found witr : erreur actionnable (06/08/2026)

| # | Micro-tâche | Statut |
|---|-------------|--------|
| W2.1 | **RED** : `test_not_found_texte_brut_remonte_cible_introuvable` — witr v0.3.3 sort le texte « no process found matching: X » sur **stderr** (exit 2, même avec `--json`) → `JsonResultFormatter` doit remonter `success: False`, `error: "Cible introuvable..."`, `data.not_found: true` (pas « Sortie JSON invalide ») ; `test_not_found_stdout_egalement_detecte` (compat rétro) | ✅ |
| W2.2 | **GREEN** : `formatters.py` — `_NOT_FOUND_RE` + `_detect_not_found(stdout, stderr)` : recherche sur les deux flux (leçon E2E : binaire réel écrit sur stderr) ; branche avant `_detect_ambiguous_targets` ; réponse inclut `stderr` tronqué pour contexte | ✅ |
| W2.3 | **VERIFY** : `pytest test_diagnostic_ext_charact + test_diagnostic_ext + test_toolbox` → **83 passed** (+1 W2) ; ruff 0 erreur | ✅ |
| W2.4 | **E2E réel** : consentement temporaire + binaire réel — `run_witr("thisprocessdoesnotexist12345")` → `{success: false, error: "Cible introuvable...", data.not_found: true, returncode: 2, stderr: "no process found..."}` ; régression nom : `run_witr("explorer")` → `success: True` inchangé ; fichier consentement nettoyé | ✅ |

**Preuve W2** :
```
pytest tests/test_diagnostic_ext_charact.py tests/test_diagnostic_ext.py tests/test_toolbox.py → 83 passed
ruff check formatters.py test_diagnostic_ext_charact.py → All checks passed!
E2E: run_witr('thisprocessdoesnotexist12345') → {'success': false, 'error': 'Cible introuvable...', 'not_found': true, 'returncode': 2}
E2E: run_witr('explorer') → {'success': true}
```

**Leçons apprises (W2)** :
- **witr v0.3.3 écrit le message « no process found » sur stderr**, pas stdout (contrairement à ce que l'audit initial avait supposé en lisant la sortie combinée). `_detect_not_found` doit scanner `stdout + "\n" + stderr` — leçon critique pour les futurs outils externes.
- Inclusion de `stderr` dans le résultat JSON (tronqué) donne à l'agent le contexte exact du binaire sans polluer `stdout` (réservé au JSON valide).
- Ordre de détection important : not-found (texte brut) AVANT ambiguïté (liste numérotée) — mutuellement exclusifs en pratique, mais not-found est plus fréquent.
- Le pattern `(?i)no matching process or service found|no process found matching` couvre les deux phrasés witr (minuscules + majuscules).

**Prochaine micro-tâche** : W3 — exit 1 (warnings witr) = succès avec ancestry complète, `success: True`, `data.warnings` conservé. Config-driven via `success_exit_codes: [0, 1]` par outil dans `diagnostic_tools.yaml`.

---

## 🔬 Audit d'intégration witr — binaire réel en main (06/08/2026)
> Relecture croisée README officiel `pranshuparmar/witr` (v0.3.3, 19.2k stars,
> release 24/06/2026 = version déployée, licence Apache-2.0) + exécution réelle
> de `bin\diagnostic\win\witr.exe` + lecture de la chaîne config → executor →
> formatter → toolbox → agent.

| Constat | Preuve binaire réelle | Sévérité |
|---|---|---|
| **P1 — Requêtes port cassées** : `run_witr("8080")` → `witr --json 8080`. witr traite les positionnels comme des **noms** (substring), pas des ports → *no process found matching: 8000* (exit 2). Bon appel : `witr --json --port 8080`. Le prompt agent (T10) invite explicitement l'utilisateur à donner « un port précis » → chemin en production cassé. Aucun E2E réel avec un vrai port (T5.2/T5.3 mockaient ou utilisaient un nom). | `witr --json 8000` → `no process found matching: 8000` ; `witr --json --port 47001` → JSON complet `{Target:{Type:"port",...}}` | 🔴 HIGH |
| **P2 — « Not found » remonte comme « Sortie JSON invalide »** : witr sort du **texte brut** (pas de JSON) même avec `--json` quand la cible n'existe pas (exit 2). `JsonResultFormatter` échoue alors sur `json.loads` → l'agent reçoit `Sortie JSON invalide: Expecting value...` au lieu de « processus introuvable ». | `witr --json thisprocessdoesnotexist12345` → texte `no process found matching: ...` exit 2 | 🟠 MEDIUM |
| **P3 — `success: False` sur une recherche réussie avec warnings** : exit code witr 1 = « trouvé avec warnings » (ex: *listening on public interface*). `JsonResultFormatter` calcule `success = returncode == 0` → une ancestry complète remonte comme échec à l'agent. | `witr --json --port 47001` → JSON valide `{Ancestry:[...], Source:{...}, Warnings:[...]}` mais exit 1 | 🟠 MEDIUM |
| P4 — `bin/VERSION.json` : entrée win witr = `sha256_zip` du zip uniquement ; le sha256 du `witr.exe` **exécuté** (`1500DC0E…`, celui de la config) n'est pas documenté → provenance incomplète | lecture VERSION.json | ⚪ LOW |
| ✅ Point de non-régression : mode ambigu vérifié réel — `witr --json svchost` → liste numérotée texte `[1]..[n]` **même avec `--json`** (exit 0) → la détection T9.2 (`_NUMBERED_LIST_RE`) est le bon mécanisme, le fixture fige un comportement réel. | `witr --json svchost` → 88 candidats `[n] svchost.exe (pid …)` | — |
| ✅ Binaire authentique : `witr --version` → `witr v0.3.3 (commit 86831e80…, built 2026-06-24T06:47:19Z)` conforme BACKLOG T1.5 ; hashes YAML/VERSION.json cohérents avec SHA256SUMS | `--version` + certutil T1.2 | — |

**Verdict** : l'intégration est **réelle et fonctionnelle pour les noms de process** (E2E T5.3) mais **incomplète** : la promesse du produit (process, port, service) n'est honorée que sur les noms. P1 est le seul bug bloquant (chemin utilisateur promis par le prompt T10), P2/P3 sont des dégradations d'UX agent.

**Prochaine micro-tâche** : W1 — requêtes port witr via `--port` (config-driven) — proposée, pas encore exécutée.

---

## 🔒 R1 — Rate limiter : purge des IPs mortes (audit interne, score 50% → fuite mémoire lente) — 06/08/2026

> Audit interne (24/07) : `services/ratelimit.py` — `_purge_stale()` existait mais **jamais appelé** → le dict `_hits` ne nettoyait jamais les IPs mortes. Fuite mémoire lente si l'API tourne longtemps / est exposée.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| R1.1 | **RED** : `test_stale_ips_purged_on_check` (tests/test_ratelimit.py) — IP morte (`[100.0]` vs now=1000.0) purgée automatiquement au check suivant ; IP vivante conservée → échoue (`dead_ip` encore dans `_hits`) | ✅ |
| R1.2 | **GREEN** : `check_rate_limit()` purge les IPs mortes en début de requête, **throttlée à 1 purge/WINDOW** (`_last_purge`) pour ne pas scanner le dict à chaque requête ; `_purge_stale(cutoff=None)` accepte un cutoff optionnel (évite un 2e appel `time.time()` → préserve le fake-time du test `test_window_expires` isolé) ; entrées à liste vide (`[]`) exclues de la purge (aucun risque mémoire, contract tests préservé) | ✅ |
| R1.3 | **VERIFY** : `pytest tests/test_ratelimit.py` → **6 passed** ; `test_window_expires` isolé → 1 passed (pas de dépendance d'ordre) ; `pytest test_ratelimit + test_api + test_security_headers` → **51 passed / 0 failed** ; `ruff check services/ratelimit.py tests/test_ratelimit.py` → All checks passed! | ✅ |

**Preuve R1** :
```
pytest tests/test_ratelimit.py → 6 passed
pytest tests/test_ratelimit.py tests/test_api.py tests/test_security_headers.py → 51 passed
ruff check services/ratelimit.py tests/test_ratelimit.py → All checks passed!
```

**Leçons apprises (R1)** :
- `_purge_stale()` existait déjà (audit §7.7) mais personne ne l'appelait — la fonction seule ne suffit pas, il faut la **câbler** au point d'entrée.
- `_purge_stale` prend le même `_lock` que `check_rate_limit` → l'appeler depuis `check_rate_limit` **sous** le lock = deadlock ; la purge doit se faire **avant** l'acquisition du lock.
- Un IP initialisé à `[]` (pattern des tests existants) est "stale" selon `not any(...)` → il faut exclure les listes vides, sinon les clés pré-seedées des tests sont purgées (KeyError).
- Le `cutoff` optionnel évite un second appel `time.time()` : indispensable pour ne pas casser `test_window_expires` qui simule le temps avec un itérateur de valeurs finies.

**Prochaine micro-tâche** : R2 (requirements-lock avec hashes SHA256) — optionnelle, usage local uniquement.

---

## 🧪 Intégration `witr` — Phase 0 (tests de caractérisation) — 06/08/2026

> Contexte : roadmap witr (process/port/service ancestry, JSON) validée. Refactos planifiés : `resolve_binary` OS-aware (Phase 2), `CommandExecutor` texte vs JSON (Phase 4), Toolbox dédup (Phase 6). La Phase 0 fige le comportement actuel AVANT tout refacto.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T0.1 | Créer `tests/test_diagnostic_ext_charact.py` — figer `format_result` (structure dict, troncatures 2000/500, sortie texte brut non parsée), `CommandExecutor.run` (court-circuits consentement/outil inconnu/binaire absent, exécution normalisée), `build_args` (plateforme win32/linux, whitelist, valeurs invalides), `resolve_binary` (win32 flat, linux PATH-first + repli bin_dir), `check_all_tools`/`list_available`/`is_ready` (structure par outil, exigence SHA256) | ✅ |
| T0.2 | `pytest tests/test_diagnostic_ext_charact.py` → **27 passed** (baseline verte) ; `ruff check` → 0 erreur | ✅ |
| T0.3 | Baseline caractérisée — prêt pour refacto Phase 1/2 | ✅ |

**Preuve T0.2** :
```
47 passed (27 caractérisation + 20 test_diagnostic_ext.py existants)
ruff check tests/test_diagnostic_ext_charact.py → All checks passed!
```

**Leçons apprises (T0.1)** :
- `run()` passe par la vérif SHA256 → pour isoler l'exécution, config `sha256: ""` (pattern des tests existants).
- `resolve_binary` Linux exige `os.path.isfile` : mocker `shutil.which` avec un vrai fichier temporaire, pas un path fictif.

**Prochaine micro-tâche** : T1.1 — Télécharger binaires witr (3 OS) → `bin/diagnostic/{win,linux,darwin}/`

### Phase 1 — Provisionnement binaires witr (3 OS) — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T1.1 | Télécharger binaires witr v0.3.3 (release officielle 24/06/2026) : `witr-linux-amd64` → `bin/diagnostic/linux/witr` ; `witr-darwin-arm64` → `bin/diagnostic/darwin/witr` ; `witr-darwin-amd64` → `bin/diagnostic/darwin/witr-amd64` ; `witr-windows-amd64.zip` → extrait → `bin/diagnostic/win/witr.exe` | ✅ |
| T1.2 | SHA256 vérifiés contre `SHA256SUMS` officiel (certutil) : linux `08fc46e3…` ✓, darwin-arm64 `d05b5182…` ✓, darwin-amd64 `39934f6a…` ✓, zip win `1ae95a35…` ✓ — 4/4 identiques | ✅ |
| T1.3 | Migrer `.exe` Sysinternals existants → `bin/diagnostic/win/` — **SANS OBJET** : le dossier `bin/diagnostic/` était vide avant ce provisionnement (aucun binaire Sysinternals présent en pré-déploiement, `config/diagnostic_tools.yaml` les déclare mais ils ne sont pas encore téléchargés) | ✅ N/A |
| T1.4 | `bin/VERSION.json` : entrée `"witr"` (v0.3.3, hashes par plateforme/arch, date) + `bin/README.md` : structure `diagnostic/{win,linux,darwin}/`, table witr, notes Gatekeeper + limitations OS | ✅ |
| T1.5 | Test rapide : `bin\diagnostic\win\witr.exe --version` → `witr v0.3.3 (commit 86831e80…)` fonctionne | ✅ |

**Preuves T1** :
```
certutil SHA256 4/4 identiques au SHA256SUMS officiel
witr.exe --version → witr v0.3.3 (commit 86831e80c59c54e19c74cdbd126ed7ff6bcad756, built 2026-06-24)
python -c json.load(VERSION.json) → JSON valide
```

**Leçons apprises (T1)** :
- Le dossier `bin/diagnostic` flat n'existait pas → la migration T1.3 est devenue inutile (rien à migrer). La structure par OS est créée proprement dès le départ.
- Le zip Windows contient `LICENSE` + `README.md` (conservés dans `bin/diagnostic/win/` pour l'audit de provenance).

**Prochaine micro-tâche** : T2.1 — Refactor `resolve_binary` OS-aware (`services/diagnostic_ext/binary.py`)

### Phase 2 — Refactor `resolve_binary` (OS-aware) — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T2.1 | `services/diagnostic_ext/binary.py` : ajout `_PLATFORM_SUBDIR = {"win32": "win", "linux": "linux", "darwin": "darwin"}` ; `platform_bin_dir = os.path.join(bin_dir, subdir)` ; Windows → `cfg["binary"]` dans le sous-dossier win ; Unix → `shutil.which()` PATH-first puis repli `darwin_binary or linux_binary or binary` sur le sous-dossier local | ✅ |
| T2.2 | Tests mis à jour flat → par-OS (`_platform_subdir` helper) : 2 tests win32/linux renommés (sous-dossier), +1 nouveau `test_darwin_resout_dans_sous_dossier_darwin` ; suite complète **828 passed / 40 skipped / 1 xfailed** (zéro régression) ; ruff 0 erreur | ✅ |
| T2.3 | Vérification manuelle : `resolve_binary({'witr': {...}}, 'witr', bin/diagnostic)` → `H:\Projet-JARVIS\bin\diagnostic\win\witr.exe` (résolution réelle win32) | ✅ |

**Preuve T2.2** :
```
pytest tests/ → 828 passed, 40 skipped, 1 xfailed
ruff check services/diagnostic_ext/binary.py + tests → All checks passed!
```

**Leçons apprises (T2)** :
- Le refactor a volontairement changé le contrat (flat → par-OS) : les tests de caractérisation Phase 0 ont été mis à jour pour refléter la **cible**, pas l'ancien comportement (c'est le but du refactor). Le comportement flat était un bug latent, pas un contrat à préserver.
- `PROJECT_DIR` vit dans `config.constants` (pas `config.paths`).

**Prochaine micro-tâche** : T3.1 — Déclaration config YAML witr (`config/diagnostic_tools.yaml`)

### Phase 3 — Déclaration config YAML (extension pure) — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T3.1 | Entrée `witr` ajoutée dans `config/diagnostic_tools.yaml` : `binary: witr.exe`, `linux_binary: witr`, `darwin_binary: witr`, `timeout: 10`, `platforms: [win32, linux, darwin]`, `output_format: json`, `args/linux_args/darwin_args: ["--json", "{target}"]`, `allowed_params: ["target"]`, `sha256: 1500DC0E…` (hash du witr.exe exécuté) — hashes Linux/darwin documentés en commentaire (support sha256 par plateforme : **fait en Phase 8**, schéma `{plateforme}_sha256` actif) | ✅ |
| T3.2 | Validation : `yaml.safe_load` OK ; `resolve_binary` trouve `bin\diagnostic\win\witr.exe` ; `check_all_tools()` → `{'available': True, 'sha256_ok': True, 'platforms': [win32, linux, darwin]}` (hash réel validé) ; 50 tests diagnostic/config passés ; ruff 0 erreur (Python) | ✅ |

**Preuve T3** :
```
check_all_tools()['witr'] → {'available': True, 'path': '...bin\\diagnostic\\win\\witr.exe', 'sha256_ok': True}
pytest test_diagnostic_ext* + test_config_files → 50 passed
```

**Leçons apprises (T3)** :
- `verify_sha256` vérifie le hash du fichier **exécuté** (witr.exe extrait, `1500DC0E…`), PAS celui du zip (`1ae95A…`) — confusion à éviter.
- Ruff ne doit PAS être lancé sur les `.yaml` (faux positifs massifs : il le traite comme du Python).
- `output_format: json` est déjà lu par la config mais pas encore consommé → Phase 4.

**Prochaine micro-tâche** : T4.1 — Refactor `CommandExecutor` : `services/diagnostic_ext/formatters.py` (Text/JSON)

### Phase 4 — Refactor `CommandExecutor` : sortie texte vs JSON — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T4.1 | `services/diagnostic_ext/formatters.py` créé : `TextResultFormatter` (comportement historique, troncatures 2000/500), `JsonResultFormatter` (parse `data`, **ne tronque pas**, erreur lisible si JSON invalide, jamais d'exception), factory `get_formatter(output_format)` avec défaut `text` | ✅ |
| T4.2 | `CommandExecutor` lit `cfg.get("output_format", "text")` dans `run()` → `get_formatter()` ; `_execute()` reçoit le formatter | ✅ |
| T4.3 | `format_result` static conservé comme wrapper délégant au formatter (défaut `text`) — compatibilité tests caractérisation Phase 0 préservée | ✅ |
| T4.4 | Tests Phase 0 → verts : 55 passed diagnostic_ext (+charact), suite complète **835 passed / 40 skipped / 1 xfailed** (828 → 835, zéro régression) | ✅ |
| T4.5 | +8 tests `TestJsonResultFormatter` : JSON valide 3000 items **non tronqué**, returncode≠0, JSON invalide → erreur lisible, stdout vide → erreur, `get_formatter` (json/text/inconnu/vide), `run()` E2E avec `output_format: json` → `data` parsé, `stdout` absent | ✅ |

**Preuve T4** :
```
pytest tests/ → 835 passed, 40 skipped, 1 xfailed (835 = 828 + 8 nouveaux - 1 renommage fusion)
ruff check services/diagnostic_ext tests/test_diagnostic_ext_charact.py → All checks passed!
```

**Leçons apprises (T4)** :
- `format_result` static conservé comme wrapper évite de casser les tests de caractérisation Phase 0 qui l'utilisent — la délégation passe par `get_formatter`, la staticmethod reste un pont de compatibilité.
- Le JSON est stocké sous `data` (pas `stdout`) : la clé `stdout` disparaît du dict JSON — contrat clair pour le frontend/agents.

**Prochaine micro-tâche** : T5.1 — `DiagnosticExtService.run_witr()`

### Phase 5 — Service `run_witr()` — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T5.1 | `DiagnosticExtService.run_witr(target)` ajouté (`service.py`) : délègue à `_run_tool("witr", extra_kwargs={"target": target})`, docstring documente que la normalisation reste côté appelant ; en-tête du module mis à jour (liste d'outils inclut witr) | ✅ |
| T5.2 | +3 tests `TestRunWitr` (caractérisation) : délégation `_run_tool("witr", extra_kwargs={"target": "nginx"})`, target port `"8080"` passé tel quel, court-circuit sans consentement ; 38 passed diagnostic_ext_charact + ruff 0 erreur | ✅ |
| T5.3 | **E2E réel** : `run_witr("explorer")` → `success: True`, `data` dict JSON avec ancestry (`ResolvedTarget`, `Process.PID/PPID/User/CPUPercent`, …) ; fichier consentement de test nettoyé | ✅ |

**Preuve T5** :
```
pytest tests/test_diagnostic_ext_charact.py → 38 passed
E2E: run_witr('explorer') → {"Target": {...}, "ResolvedTarget": "Explorer.EXE", "Process": {...}}
```

**Leçons apprises (T5)** :
- witr passe en **mode interactif (texte, pas JSON)** quand plusieurs process matchent le target (ex: `svchost` → liste numérotée [1]..[n]). Le `--json` ne s'applique qu'à un match unique. → À refléter dans le prompt agent (Phase 7) : cibler un nom/port précis, pas un préfixe ambigu.
- `--container` renverra plusieurs conteneurs → la non-troncature JSON (Phase 4) est essentielle.

**Prochaine micro-tâche** : T6.1 — Toolbox : charger triggers depuis `config/toolbox_triggers.yaml` (dédup) + trigger `why_running`

### Phase 6 — Toolbox : dédup triggers YAML + witr — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T6.1 | `services/toolbox.py` réécrit : triggers chargés depuis `config/toolbox_triggers.yaml` (source de vérité unique) au lieu de la liste hardcodée. Mapping `tool_name -> méthode` (`_DIAGNOSTIC_TOOLS`, `_FILE_TOOLS`) ; dispatch des arguments par `key` (`_invoke_diagnostic`/`_invoke_file`) ; `describe_tools()` généré depuis le YAML ; les autres triggers YAML (kill_*, code_review_*, quality_audit) **non gérés par Toolbox sont ignorés** (code mort vérifié par grep : rien ne les consomme) ; `TRIGGERS_CONFIG` (`config/paths.py`, déjà présent mais inutilisé) est désormais consommé | ✅ |
| T6.2 | Trigger witr ajouté au YAML : `key: why_running`, `tool: witr`, keywords [pourquoi, why, running, tourne, ancestry, port occupe…], description "explique pourquoi un processus/port/service tourne (witr)" | ✅ |
| T6.3 | Non-régression : keyword YAML identiques à l'ancienne liste hardcodée (vérifié via `git show HEAD`), tests Toolbox passent ; +2 tests (`test_auto_execute_why_running_trigger_loaded_from_yaml`, `test_extract_target_witr`), `_extract_target` avec filtre stopwords FR/EN (pourquoi nginx → nginx ; port 8080 → 8080 ; explorer → explorer ; mysql → mysql) | ✅ |
| T6.4 | Liste hardcodée `self._diagnostic_triggers` supprimée du code (`describe_tools`/`auto_execute`/`_format_stdout` réécrits génériquement) ; E2E réel : trigger `why_running` déclenché → routé vers `run_witr` (échoue proprement sans consentement, par design) | ✅ |

**Preuve T6** :
```
pytest tests/test_toolbox.py → 17 passed (suite complète : 838 passed, 40 skipped, 1 xfailed)
ruff check services/toolbox.py tests/test_toolbox.py → All checks passed!
E2E: Toolbox().auto_execute("pourquoi le processus explorer tourne") → {'why_running': {'tool': 'witr', 'success': False, 'error': 'Consentement non donné'}}
```

**Leçons apprises (T6)** :
- Le YAML contenait des triggers (kill_*, code_review_*, quality_audit) jamais consommés par aucun service (vérifié par grep) — code mort historique, désormais explicitement documenté comme "hors Toolbox" dans le module.
- `_extract_target` naïve (dernière token) échouait sur les stopwords → filtre stopwords FR/EN nécessaire ; "why is this running" sans target → mode global witr (fallback acceptable, documenté pour Phase 7).
- Le consentement (.diagnostic_consent) restreint aussi witr : l'échauffement est propre ("Consentement non donné"), pas de crash.

**Prochaine micro-tâche** : T7.1 — Agents : intégrer witr dans agent @hardware (API `run_witr` + trigger `why_running` déjà routé côté Toolbox)

### Phase 7 — Agents : routage YAML (KISS/SOLID) + wiring witr — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T7.1 | Refacto `services/router.py` : config YAML = **source de vérité unique** (`config/agent_routing.yaml`, désormais lu via `ROUTING_CONFIG`). `AgentRoutingConfig` frozen dataclass (thread-safe), `load_routing_config()` avec dégradation gracieuse (YAML absent/corrompu → fallback `dev`, warning loggé), dicts hardcodés supprimés (DRY). Mots-clés hardware witr ajoutés au YAML (`processus, tourne, running, pourquoi, why`) | ✅ |
| T7.2 | Fix bug T1 (audit Claude) : `services/pipeline_steps.py` lisait `state.get("context", {})` **2×** (L65,L84) → dicts différents si la clé manque, `tool_results` witr perdu silencieusement hors du chemin `agent_graph` (qui pré-remplit `context`). Fix : `state.setdefault("context", {})` + passage de la même variable à `agent.run()` | ✅ |
| T7.3 | Contrat agent `@hardware` figé : `create_agents()` → `_domain_prompt` contient `why_running`/`witr` (factory déjà enrichie en T6 worktree) + test E2E prompt LLM | ✅ |
| T7.4 | **E2E réel** sans consentement : `AgentGraph.run("pourquoi le processus explorer tourne")` → `agent_key=hardware` (YAML), `tool_results.why_running` présent dans le context de l'agent, witr court-circuite proprement (« Consentement non donné »), aucun artefact créé | ✅ |

**Preuve Phase 7** :
```
pytest tests/ → 858 passed, 40 skipped, 1 xfailed  (840 → 858 = +11 router_config +7 pipeline_steps)
ruff check . → All checks passed!
pytest test_router*.py → 27 passed (contract préservé) ; test_pipeline_steps.py → 7 passed ; test_toolbox.py → 19 passed ; test_agents.py → 34 passed
E2E: AgentGraph.run('pourquoi le processus explorer tourne') → agent_key=hardware, tool_results['why_running']={'success': False, 'error': 'Consentement non donné'}
```

**Leçons apprises (T7)** :
- Pletcher Toolbox : le déclencheur `fn` est capturé **à l'init** (`_load_*_triggers`), pas à l'éxécution → pour tester witr routé, patcher la **classe** `DiagnosticExtService.run_witr` puis reconstruire le Toolbox (patcher l'instance après init ne fait rien).
- `AgentRouter` est instancié sans argument partout (`di.py`, tests) → le constructeur doit charger le YAML par défaut ; injection de config réservée aux tests (DIP).
- La dégradation gracieuse du loader impose un garde sur `max(scores)` **(keyword_map vide → ValueError)** : `if scores else None`.

**Prochaine micro-tâche** : Phases 8-10 ci-dessous (sha256 par plateforme, mode interactif witr, prompt agent finalisé) — `bin/README.md`/`VERSION.json` déjà à jour.

### Phase 8 — SHA256 par plateforme (Gap 1, bug silencieux) — 06/08/2026

> Audit préalable : `config/diagnostic_tools.yaml` ne déclare qu'une seule clé `sha256` (hash Windows, commentaires L88-92 documentant les hashes linux/darwin jamais exploités) ; `service.py::_check_tool` fait `cfg.get("sha256", "")` sans branchement plateforme → `sha256_ok` toujours `False` hors Windows. `executor.py:67` porte le même bug (échec SHA256 en run sous Linux). Aucun test ne caractérisait ce cas.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T0.4 | Fix baseline : import cassé `resolve_sha256` (fonction jamais écrite) dans `tests/test_diagnostic_ext_charact.py:26` → rejeu 129 passed (109 annoncés + 20) | ✅ |
| T8.1 | **RED** : `test_check_tool_witr_linux_utilise_hash_linux` (patch global `sys.platform` — couvre binary.py ET service.py) → échoue : `sha256_ok is False` car comparaison au hash win32 (bug exact) | ✅ |
| T8.2 | `config/diagnostic_tools.yaml` : schéma `{plateforme}_sha256` appliqué à **toutes** les entrées — witr : `linux_sha256` `08fc46e3…` + `darwin_sha256` `d05b5182…` (arm64 déployé, hashes réels vérifiés T1.2) ; autres outils : clés vides documentées (aucun hash linux/darwin connu) ; commentaire « Phase 10 » obsolète supprimé | ✅ |
| T8.3 | `resolve_expected_sha256(config, tool_name, platform)` ajouté dans `binary.py` (signature alignée sur `resolve_binary`, même responsabilité) : win32 → `sha256`, sinon → `{platform}_sha256` avec repli `sha256`. Consommé par `service.py::_check_tool` ET `executor.py::run` (même bug silencieux — échec SHA256 au run hors Windows) | ✅ |
| T8.4 | **GREEN** : rejeu complet `pytest tests/` → **863 passed / 40 skipped / 1 xfailed** (zéro régression) | ✅ |
| T8.5 | **E2E réel** : `check_all_tools()` mock `sys.platform="linux"` → `witr.sha256_ok True` (hash linux réel `08fc46e3…` vs binaire `bin/diagnostic/linux/witr`) ; win32 inchangé `True/True` | ✅ |
| T8.6 | `BACKLOG.md` (L74/L177) + `bin/README.md` : note « Phase 10 » obsolète retirée, schéma `{plateforme}_sha256` documenté | ✅ |

### Phase 9 — Mode interactif witr (Gap 2, cible ambiguë) — 06/08/2026

> Leçon T5 jamais traitée : witr bascule en **texte brut** (liste numérotée `[1]..[n]`, pas JSON) quand plusieurs process matchent le target (ex: `svchost`). `JsonResultFormatter` le confondait avec une erreur JSON générique → texte brut non parsé remonté à l'agent LLM. Aucun extrait réel archivé : le fixture de test fige le pattern documenté par la leçon T5.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T9.1 | **RED** : `test_mode_interactif_liste_numerotee_distinguce_d_erreur_json` (fixture `WITR_AMBIGUOUS_STDOUT`, 3 lignes `[n] …`) → échoue : le formatter renvoie « Sortie JSON invalide » | ✅ |
| T9.2 | `JsonResultFormatter` : détection du pattern liste numérotée witr (regex `\[\d+\]`, ≥ 2 entrées) → retourne `success: False` + `data={"ambiguous": True, "candidates": [...]}` + erreur explicite « Cible ambiguë : N processus correspondent » ; repli inchangé sur « JSON invalide » sinon (contrat Phase 4 préservé) | ✅ |
| T9.3 | **GREEN** : `test_run_witr_cible_ambigue_remonte_data_ambiguous` (service complet, subprocess mocké) → `data.ambiguous True`, `candidates` peuplé ; cas nominal single-match toujours vert ; 60 passed (charact 41 + toolbox 19) | ✅ |
| T9.4 | **E2E réel** : `AgentGraph.run("pourquoi svchost tourne")` (AgentRouter + create_agents + Toolbox, `run_witr` mocké en classe — leçon T7) → `agent_key=hardware`, `tool_results.why_running.data.ambiguous True`, `candidates` 3, aucun crash | ✅ |

### Phase 10 — Prompt agent : disambiguation (Gap 3, dépend de T9.2) — 06/08/2026

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T10.1 | **RED** : `test_hardware_domain_prompt_geres_cible_ambigue` (extension pattern T7.3) → échoue : le prompt `@hardware` ne contient ni « ambig » ni « PID » | ✅ |
| T10.2 | `agents/factory.py` : une phrase ajoutée au `domain_prompt` hardware — si `ambiguous` (plusieurs process), demander un PID ou un port précis avant de conclure | ✅ |
| T10.3 | **GREEN** : `pytest tests/` → **866 passed / 40 skipped / 1 xfailed** (zéro régression) ; `ruff check .` → **All checks passed!** (2 fixes : variable `context` inutilisée test_agents, import `platform` inutilisé charact) | ✅ |

**Preuve T10** :
```
pytest tests/ → 866 passed, 40 skipped, 1 xfailed
ruff check . → All checks passed!
```

**Leçons apprises (T10)** :
- Le test T10.1 est un test de prompt statique (`_domain_prompt` figé par `create_agents`) : le contexte `tool_results.ambiguous` injecté est documentaire — l'assertion porte sur le texte du prompt, pas sur le flux (le flux est déjà couvert par T9.4).
- La variable `context` du test ne servait à rien côté assertion → supprimée (F841), et l'import `platform` du fichier charact était un reliquat de la Phase 0 (jamais utilisé).

### Audit go/nogo witr rejoué — P1/P2 déjà closes, verdict invalide (06/08/2026)

> L'audit go/nogo « Intégration witr » (verdict NO-GO sur Linux/Darwin) a été relu
> après l'exécution des Phases 8-10 : il figeait l'état AVANT ces phases. Rejeu
> réel (grep + lecture code + tests) :

| Point audit | Réalité code | Preuve |
|---|---|---|
| P1 : hash unique bloque `run()` hors Windows | **Clos** — `resolve_expected_sha256` (binary.py:66), consommé par executor.py:67 ET service.py:135 ; `linux_sha256`/`darwin_sha256` actifs (yaml L103-104) | test_check_tool_witr_linux_utilise_hash_linux (charact:536) |
| P2 : mode interactif dégradé non caractérisé | **Clos** — `_detect_ambiguous_targets` (formatters.py:80) → `data.ambiguous True` + `candidates`, erreur « Cible ambiguë » | charact:345,435 (T9.3) |
| Prompt agent disambiguation | **Clos** — agents/factory.py:77-79 demande PID/port si `ambiguous` | test_agents.py:375 (T10.1) |

**Preuve rejeu complet** : `pytest tests/` → **866 passed / 40 skipped / 1 xfailed**
(identique à T10.3) ; `ruff check .` → **All checks passed!**

**Conclusion** : les conditions de GO de l'audit (1. P1, 2. P2, 3. zéro régression)
sont toutes satisfaites. Pas de nouvelle micro-tâche requise.

---

### Fin de l'intégration witr — Phase 8-10 closes (06/08/2026)

- **Gap 1 (sha256 par plateforme)** : bug silencieux corrigé — `resolve_expected_sha256()` suit le même schéma que `resolve_binary` (win32 → `sha256`, sinon `{platform}_sha256` avec repli), appliqué à `_check_tool` ET `executor.run` (le bug existait aux deux endroits). Hashes réels witr linux/darwin déclarés (vérifiés T1.2).
- **Gap 2 (mode interactif witr)** : la sortie liste numérotée `[1]..[n]` est désormais caractérisée — `data={"ambiguous": True, "candidates": [...]}` + erreur explicite, remontée proprement au contexte agent (E2E AgentGraph vérifié).
- **Gap 3 (prompt agent)** : l'agent `@hardware` demande un PID/port précis en cas de cible ambiguë.
- **Compteur de tests** : 863 → 866 (T8.1, T9.1, T9.3, T10.1 = +4 tests depuis la baseline 862 ; T0.4 a réparé l'import cassé qui empêchait la collection du fichier charact).

---

**Projet** : JARVIS Portable Edition v5.5
**État réel vérifié** (08/08/2026) : 903+ passed / échecs pré-existants hors périmètre (test_model_tags_consistency + 3 tests d'intégration Ollama, cf. W-TIMEOUT) / 40 skipped / 1 xfailed
**Méthode d'audit** : relecture du BACKLOG.md précédent + grep/lecture du code réel derrière chaque item + relance de la suite de tests + `git log`/`git status`
**Verdict global** : JARVIS opérationnel sur la clé USB — 7 modèles HF pull réels, serveur démarré, chat fonctionnel (see W-DEPLOY 4-6, P-REPAIR, W-TIMEOUT). Sessions 25-26/07 closes (historique compressé ci-dessous).

---

## 🗄️ Historique compressé — sessions closes du 25→26/07/2026

> Compressé le 08/08/2026 : les blocs RED/GREEN détaillés des sessions closes sont
> synthétisés ci-dessous. Le détail complet reste consultable dans l'historique git
> (`git log --oneline`, `git show <sha>`).

| Session | Synthèse | Commit |
|---------|----------|--------|
| 0.1 Commit en attente | `docs: aligne README suite au retrait de .opencode/` — CLOSED | `2283b6b` |
| Phase 7.4 Sécurité | error leakage : `vectorize_conversations` masque l'erreur brute + log `exc_info=True` | `7747ad2` |
| Phase 8 Perf | I/O orjson : large writes **4x** P50 (58,9→14,4 ms), reads *1,8 ; batch writes ; `rapport_perf.md` | 8.4 |
| Phase 9 UX | 9.1 focus trap modals ; 9.2 skeletons Skills/Analytics ; 9.3 toasts feedback ; 9.4 dark mode persisté (localStorage) | — |
| Phase 10 Docs | ROADMAP Phases 7-9, CHANGELOG v5.5, garde-fou headers (X-XSS-Protection jamais envoyé) | — |
| 10.4/10.5 | RAS (`os.system` absent) ; stubs legacy `_check_ollama`/`_sync_module_globals` supprimés (code mort) | `4b00bac` |
| Phase 11 | Ruff 0 erreur — détail ci-dessous | `09f4318` |
| Phase 12 | UI : 12.1 sidebar mobile (<768 px), 12.2 contraste thème clair, 12.3 CSS mort | — |
| Phase 13 | Migration 100 % HuggingFace — 24 fichiers, 7 blocs `hf.co/...` | — |

**Phase 11 (détail)** : W291/W292/W293 + UP035/UP015/UP006/E401/W605/F541 (whitespace/typing, 62 fichiers) ;
F401 ×37 supprimés + protection `__all__` des ré-exports (`BIN_LINUX`/`BIN_MAC`) ; I001 ×44 imports triés ;
E402 + `# noqa: E402  # avoid circular import` ×26 ; F811 ×2 renommés ; F841, N802 ×2, N806, SIM108, SIM117 ;
livré en 2 commits → `ruff check . --statistics` : 0 erreur.

**Phase 12 (détail)** : 12.1 bouton `#hamburger` + backdrop + toggle `.show` ; 12.2 `.msg pre`
et `.skill-card` → `color: var(--text)`, `.fb-breadcrumb` → `var(--panel-2)` ; 12.3 suppression
`.tool-card /.btn-run/.btn-dl/.badge-fallback` (CSS mort).

**Phase 13 (détail)** : Qwen2.5-7b, granite-4.1-8b, DeepHat-V1-7B, Foundation-Sec-8B-Reasoning,
phi-4-mini, Llama-3.2-11B-Vision, nomic-embed-text-v2-moe → noms `hf.co/...` propagés dans config,
services, selector, frontend, tests, docs ; `config/model_sizes.json` mis à jour.

---

---

és et corrigés — 07/08/2026

> Contexte : test de déploiement guidé pas-à-pas sur PC Windows réel, clé USB
> H:\Projet-JARVIS déjà clonée (pas de git clone/format). Suivi strict du guide
> README section Installation. Deux blocages réels rencontrés, reproduits, corrigés
> en RED/GREEN, avec preuve empirique sur zip réel avant correctif.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| D.1 | **Bug réel #1** : `scripts\install.py` → `setup_ollama()` détecte un Ollama système (`shutil.which("ollama")`) et s'arrête sans jamais préparer `bin\ollama.exe` — mais `print_final()` affiche quand même sans condition « 1. Lancer Ollama : bin\ollama.exe serve » → `Start-Process` échoue en réel (« fichier introuvable ») | ✅ reproduit en réel |
| D.2 | **RED** : `test_install_final_message.py` (`print_final(ollama_portable_path=None)` ne doit pas contenir `bin\ollama.exe serve`) → confirmé en échec sur l'ancien code (rejoué à l'identique pour preuve) | ✅ |
| D.3 | **GREEN** : `_portable_ollama_path()` ajoutée (détecte le binaire portable réel sur la clé) ; `print_final()` accepte `ollama_portable_path` et n'affiche `bin\ollama.exe serve` que si le binaire existe réellement, sinon `ollama serve` + mention installation système | ✅ |
| D.4 | Contournement manuel en session réelle pendant l'attente du fix : `python -c "from services.ollama_installer import _install_windows_zip; print(_install_windows_zip(lambda *a: None))"` → a débloqué `bin\ollama.exe`, mais a révélé le bug D.5 | ✅ |
| D.5 | **Bug réel #2** : `_install_windows_zip` extrait toute l'archive Windows dans un dossier temp, ne copie que `ollama.exe` vers `bin\`, puis supprime le dossier temp dans le `finally` → perte définitive de `lib\ollama\llama-server.exe` + DLL GPU → serveur Ollama démarre mais log `"failure during llama-server GPU discovery"`, aucune inférence possible | ✅ reproduit en réel (logs Ollama collés par Michel) |
| D.6 | **RED** : `test_windows_zip_lib_extraction.py` — zip factice imitant la structure réelle (`ollama.exe` + `lib/ollama/llama-server.exe` + DLL), assert que `llama-server.exe` survit à `_install_windows_zip` → confirmé en échec avant correctif | ✅ |
| D.7 | **GREEN** : `_install_windows_zip` copie désormais aussi `lib/ollama/` vers `BASE_DIR/lib/ollama/` (`shutil.copytree(dirs_exist_ok=True)`), en miroir de ce que fait déjà `_install_linux_tar` pour Linux (candidat déjà sondé nativement par Ollama : `H:\Projet-JARVIS\lib\ollama\llama-server.exe`) | ✅ |
| D.8 | **VERIFY** : suite complète `pytest tests/` → **882 passed / 0 failed / 40 skipped / 1 xfailed** (vs 879 avant, +3 tests), ruff clean sur les 4 fichiers touchés | ✅ |

**Preuve D** :
```
RED  (ancien code) : test_print_final_no_portable_binary_does_not_reference_bin_ollama → FAILED
                      (assert 'bin\\ollama.exe serve' not in out → False)
GREEN (corrigé)     : 2 passed (test_install_final_message.py)
RED  (ancien code) : test_install_windows_zip_preserves_llama_server → FAILED
                      (llama-server.exe absent après installation)
GREEN (corrigé)     : 1 passed (test_windows_zip_lib_extraction.py)
Suite complète      : 882 passed, 40 skipped, 1 xfailed, ruff All checks passed!
```

**Leçons apprises (W-DEPLOY)** :
- Aucun des deux bugs n'était couvert par la suite existante (0 test sur `setup_ollama`/`print_final`, 0 test sur le contenu copié par `_install_windows_zip`) — les audits go/nogo précédents (754→879 passed) portaient sur l'app FastAPI/tests unitaires, jamais sur un déploiement Windows réel de bout en bout. Un simulateur pytest ne peut pas attraper un bug qui ne se manifeste qu'au téléchargement réel d'une archive tierce.
- Le pattern `_install_linux_tar` gérait déjà correctement `lib/ollama/` — le portage Windows (`_install_windows_zip`) avait été fait en copiant seulement l'exécutable, sans reprendre cette partie. Dette de cohérence entre les deux implémentations, jamais testée en miroir.
- `get_ollama_path()` retombe silencieusement sur `shutil.which()` (PATH système) si rien n'est trouvé en portable — comportement voulu pour permettre l'usage d'un Ollama système, mais qui rend `setup_ollama()` "silencieusement non-portable" par défaut dès qu'un Ollama global existe sur le PC. Non corrigé ici (hors périmètre du blocage immédiat) : à surveiller si l'objectif "100% portable, zéro dépendance système" doit être strict.

**Fichiers livrés (session, non encore commités)** : `services/ollama_installer.py`, `scripts/install.py`, `tests/test_windows_zip_lib_extraction.py`, `tests/test_install_final_message.py`

**Prochaine micro-tâche** : rejouer le guide README de bout en bout sur le même PC avec les fichiers corrigés (téléchargement des 7 modèles restant à faire au moment de la rédaction), puis vérifier `curl /api/status` + `/api/agents` en conditions réelles.

---

## 🔧 W-DEPLOY-2 — README : 5 des 7 repos HF de pull modèles cassés — 07/08/2026

> Suite directe de W-DEPLOY. Pendant le pull réel des 7 modèles sur le déploiement
> Windows en cours, 3 échecs consécutifs sur 4 tentatives (voir preuves ci-dessous).
> Décision de Michel : arrêter le debug live modèle par modèle, corriger le README
> une bonne fois pour toutes en recherchant chaque repo avant de le publier.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| D2.1 | **Bug réel #1 (E2E)** : `hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M` → `400 sharded GGUF, Ollama does not support this yet` (issue ollama/ollama#5245, toujours ouverte) | ✅ reproduit en réel |
| D2.2 | **Bug réel #2 (E2E)** : `hf.co/ibm-granite/granite-4.1-8b-instruct-GGUF:Q4_K_M` → `realm host "huggingface.co" does not match original host "hf.co"` (repo inexistant sous ce nom — le repo IBM officiel est `granite-4.1-8b-GGUF`, sans `-instruct`) | ✅ reproduit en réel |
| D2.3 | **Bug réel #3 (E2E)** : `hf.co/mradermacher/DeepHat-V1-7B-i1-GGUF:Q4_K_M` → même erreur `realm host` (repo existe mais tag/nommage incompatible avec le pull Ollama) | ✅ reproduit en réel |
| D2.4 | **Recherche + correction des 7 repos** : chaque repo HF vérifié individuellement (fichier unique non-sharded, existence confirmée) avant remplacement dans le README | ✅ |
| D2.5 | **RED** : `test_readme_hf_repos_no_longer_reference_broken_sources` + `test_readme_hf_repos_reference_verified_replacements` (`tests/test_readme_install_consistency.py`) → échouent sur l'ancien README | ✅ |
| D2.6 | **GREEN** : README corrigé sur les 3 blocs (Windows §Étape 5, Linux, macOS) + tableaux de poids (2×) + note de traçabilité historique inline | ✅ |
| D2.7 | **VERIFY** : suite complète → **884 passed / 0 failed / 40 skipped / 1 xfailed** (vs 882 avant, +2 tests), ruff clean | ✅ |

**Repos corrigés (7)** :

| Modèle | Repo cassé (README v5.6) | Repo corrigé | Vérification |
|---|---|---|---|
| Qwen2.5-7B-Instruct | `Qwen/Qwen2.5-7B-Instruct-GGUF` (sharded) | `bartowski/Qwen2.5-7B-Instruct-GGUF` | ✅ **pull réel réussi** (4,7 Go) |
| Granite-4.1-8B | `ibm-granite/granite-4.1-8b-instruct-GGUF` (404) | `bartowski/ibm-granite_granite-4.1-8b-GGUF` | ✅ **pull réel réussi** (5,5 Go) |
| DeepHat-V1-7B | `mradermacher/DeepHat-V1-7B-i1-GGUF` (tag invalide) | `GGUF-A-Lot/DeepHat-V1-7B-GGUF` | ✅ **pull réel réussi** (5,3 Go) |
| Foundation-Sec-8B-Reasoning | `fdtn-ai/Foundation-Sec-8B-Reasoning-GGUF:Q4_K_M` (repo par-quant, pas de tag générique ; pas de variante Q4_K_M publiée pour "Reasoning") | `fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF:Q8_0` | ✅ **pull réel réussi** (8,5 Go) — poids révisé ~4,9→~8,5 Go |
| Phi-4-mini-abliterated | `Melvin56/Phi-4-mini-instruct-abliterated-GGUF` | inchangé | ✅ **pull réel réussi** (2,5 Go) |
| Llama-3.2-11B-Vision-Instruct | `bartowski/Llama-3.2-11B-Vision-Instruct-GGUF` (bartowski n'a jamais publié ce modèle vision — confirmé par son propre commentaire HF de 2024 : *"Llama.CPP can't run those vision models yet"*) | `leafspark/Llama-3.2-11B-Vision-Instruct-GGUF` | ✅ **pull réel réussi** (6,0 Go + 1,9 Go mmproj) |
| nomic-embed-text-v2-moe | `nomic-ai/nomic-embed-text-v2-moe-GGUF` | inchangé | ✅ **pull réel réussi** (344 Mo) |

**Leçons apprises (W-DEPLOY-2)** :
- Les échecs de pull HF via Ollama se répartissent en 2 familles distinctes, à diagnostiquer différemment : (a) `sharded GGUF` = fichier multi-parties, incompatible par design avec `ollama pull hf.co/...` (limitation Ollama elle-même, pas corrigible côté JARVIS) ; (b) `realm host does not match` = repo/tag inexistant côté HF (faute de frappe ou repo jamais publié sous ce nom), corrigible en changeant de repo miroir (bartowski, GGUF-A-Lot, leafspark... republient couramment les mêmes poids en fichier unique).
- Certains éditeurs (fdtn-ai) publient **un repo HF par niveau de quantization** au lieu d'un repo unique multi-tags — le pattern `hf.co/<repo>:<QUANT>` du reste du README ne s'applique pas tel quel, il faut alors viser directement le repo du quant voulu avec `:latest` ou le nom du quant en tag si le repo n'a qu'un seul fichier.
- Écart assumé initialement pour 2 des 7 corrections (vérification "repo existe" par
  recherche web, pas encore de pull réel) — **clos le jour même** : les 7 modèles ont
  été pull réel avec succès sur le déploiement Windows en cours (H:\Projet-JARVIS),
  y compris les 2 restants (`Foundation-Sec-8B-Reasoning-Q8_0`, `Llama-3.2-11B-Vision-Instruct`).

**VERIFY final (E2E, 07/08/2026)** : 7/7 modèles téléchargés avec succès sur déploiement
Windows réel — `Qwen2.5-7B-Instruct` (4,7 Go), `granite-4.1-8b` (5,5 Go), `DeepHat-V1-7B`
(5,3 Go), `Foundation-Sec-8B-Reasoning-Q8_0` (8,5 Go), `phi-4-mini-instruct-abliterated`
(2,5 Go), `Llama-3.2-11B-Vision-Instruct` (6,0 Go + 1,9 Go mmproj), `nomic-embed-text-v2-moe`
(344 Mo) — digest SHA256 vérifié à chaque pull, aucun échec.

**Fichiers livrés (session, non encore commités)** : `README.md`, `tests/test_readme_install_consistency.py` (2 tests ajoutés)

**Prochaine micro-tâche** : lancer `launchers\JARVIS.bat`, vérifier `curl /api/status` +
`/api/agents` en conditions réelles, puis contrôler que `config/model_sizes.json` /
`services/selector.py` référencent bien les noms de modèles Ollama réellement présents
(`ollama list`) et pas les anciens tags cassés — point de vigilance signalé en fin de
W-DEPLOY-2, non encore vérifié.

---

## 🔧 W-DEPLOY-3 — 71 références aux anciens tags cassés dans 21 fichiers du code — 07/08/2026

> Suite directe de W-DEPLOY-2. Point de vigilance signalé en fin de session précédente
> ("les nouveaux noms de modèles ne matchent plus forcément les clés attendues par
> config/model_sizes.json, services/selector.py") — confirmé fondé après vérification.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| D3.1 | **Recherche exhaustive** : `grep -rl` des 5 tags cassés sur tout le repo → 21 fichiers touchés (config prod, sélecteur de modèles, adaptateur Ollama, frontend JS, script smoke-test, doc MODELS.md, AGENTS.md ×2, RUNBOOK.md, 10 fichiers de tests) | ✅ |
| D3.2 | **RED** : `test_no_broken_model_tags_in_tracked_source` (`tests/test_model_tags_consistency.py`) — scan de tous les fichiers `git ls-files` texte (hors BACKLOG.md, changelog légitime) → confirmé en échec sur l'état d'origine (54 occurrences, `git stash` + rejoué pour preuve) | ✅ |
| D3.3 | **GREEN** : remplacement des 5 tags cassés par leurs équivalents vérifiés dans les 21 fichiers (71 occurrences au total) — mêmes correspondances que W-DEPLOY-2 | ✅ |
| D3.4 | **VERIFY** : JSON validés (`config/model_sizes.json`, `config/agent_profiles.json`), suite complète → **883 passed / 0 failed / 40 skipped / 1 xfailed** (vs 882 après sync origin/main, +1 test), ruff clean | ✅ |

**Fichiers touchés (21, hors README/BACKLOG déjà faits en W-DEPLOY-2)** :
`config/model_sizes.json`, `config/constants.py`, `config/agent_profiles.json`,
`services/selector.py`, `services/adapters/ollama_adapter.py`,
`static/assets/js/app.js`, `scripts/smoke_test_frontend_api.py`,
`models/ollama/MODELS.md`, `AGENTS.md`, `.opencode/AGENTS.md`, `docs/RUNBOOK.md`,
`tests/test_integration_ollama.py`, `tests/test_model_llama_vision.py`,
`tests/test_model_bartowski.py`, `tests/test_model_ornith.py`,
`tests/test_offline_enforcement.py`, `tests/test_model_qwen25.py`,
`tests/test_api_fuzz.py`, `tests/test_agents.py`, `tests/conftest.py`,
`tests/test_selector.py`

**Anomalie annexe découverte** : le fichier `tests/test_readme_install_consistency.py`
livré en W-DEPLOY-2 (2 tests ajoutés) n'a **jamais été committé** — `git status` sur
la clé ne l'a jamais listé comme modifié après copie, confirmé par
`git show origin/main:tests/test_readme_install_consistency.py` (3 tests seulement,
pas 5). Cause probable : le fichier n'a pas été effectivement écrasé sur `H:\Projet-JARVIS`
lors de la copie manuelle. Re-livré avec cette session, à committer.

**Leçons apprises (W-DEPLOY-3)** :
- Corriger un README ne corrige rien côté application si le code prod référence les
  mêmes identifiants en dur ailleurs — la documentation et la config peuvent diverger
  silencieusement sans qu'aucun test ne le détecte, sauf à écrire un test qui scanne
  le repo entier plutôt qu'un fichier précis. `test_model_tags_consistency.py`
  comble ce trou durablement (toute réintroduction future d'un tag cassé fera échouer
  la suite, quel que soit le fichier).
- La copie manuelle de fichiers livrés par chat vers une clé USB est un point de
  fragilité non technique : un fichier peut silencieusement ne pas être remplacé
  sans qu'aucune erreur ne le signale (`git status` ne peut détecter que ce qu'il
  voit sur disque). Vérifier `git status` après chaque copie reste la meilleure
  garde-fou disponible côté utilisateur.

**Fichiers livrés (session, non encore commités)** : les 21 fichiers listés ci-dessus,
`tests/test_model_tags_consistency.py` (nouveau), `BACKLOG.md`, et le re-livrable
`tests/test_readme_install_consistency.py` (2 tests manquants du commit précédent).

**Prochaine micro-tâche** : `git add` de tous ces fichiers + commit + push, puis
relancer `launchers\JARVIS.bat` et vérifier `curl /api/status` + `/api/agents` +
`/api/agents/assign` pour confirmer que JARVIS résout bien les modèles sous leurs
nouveaux noms auprès d'Ollama en conditions réelles.

---

## 🔧 W-DEPLOY-4 — `jarvis.py` : ModuleNotFoundError uvicorn au premier lancement réel — 07/08/2026

> Suite directe de W-DEPLOY-3 : premier lancement réel de `launchers\JARVIS.bat`
> sur H:\Projet-JARVIS avec toutes les corrections précédentes en place (binaire
> Ollama présent, 7 modèles pull, imports OK annoncé par le .bat). Crash immédiat
> malgré tout. Refacto SOLID (SRP) plutôt qu'un patch inline dans jarvis.py.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| D4.1 | **Bug réel #1 (E2E)** : `launchers\JARVIS.bat` → `[ERREUR] JARVIS s'est arrêté avec le code 1`. `logs\jarvis_core.log` → `ModuleNotFoundError: No module named 'uvicorn'` sur `jarvis.py:13`. Cause : `import uvicorn` en tête de module, avant que `ensure_venv()` (qui installe les dépendances manquantes) n'ait la moindre chance de s'exécuter | ✅ reproduit en réel (log collé par Michel) |
| D4.2 | **Bug réel #2 (audit, non bloquant pour ce déploiement)** : `preflight_check()` passe le `logging.Logger` brut à `ensure_ollama_binary()`, qui attend un callable `log(step, message, success)` → `TypeError: 'Logger' object is not callable` si le binaire Ollama est absent. Sans impact ici (`bin\ollama.exe` déjà présent sur la clé → retour anticipé avant l'appel fautif), mais bloquerait un premier déploiement sans binaire pré-livré | ✅ identifié, non exercé en réel (branche non atteinte sur cette clé) |
| D4.3 | **RED** : reproduction fidèle en sandbox — `import jarvis` avec `uvicorn` absent de l'interpréteur → `ModuleNotFoundError` confirmé au niveau module (même mécanisme que le crash réel) | ✅ |
| D4.4 | **GREEN — refacto SRP** (3 fichiers) : `services/log_adapter.py` (nouveau, responsabilité unique : adapter `logging.Logger` → callback `(step, message, success)`) ; `services/dependency_bootstrap.py` (nouveau, responsabilité unique : `bootstrap_dependencies(logger)` — délègue à `ensure_venv()` puis relance via `os.execv` si l'interpréteur choisi diffère du courant, comparaison en `abspath` et non `realpath` pour ne pas confondre un venv symlinké avec l'interpréteur système) ; `jarvis.py` redevient un composition root pur — `import uvicorn` / `from dotenv import load_dotenv` déplacés dans `main()`, après l'appel à `bootstrap_dependencies()` | ✅ |
| D4.5 | **VERIFY** : `import jarvis` sans `uvicorn` installé → OK, aucun `ModuleNotFoundError`, aucun provisioning déclenché au simple import (non-régression sur `test_jarvis_shutdown.py` / `test_ollama_port_single_source.py`) ; tests ciblés `bootstrap_dependencies` (mêmes interpréteur → pas de relance / interpréteur différent → relance `os.execv`) et `to_step_logger` (callable `(step, message, success)`) → passent ; suite complète → **882 passed / 1 failed (faux positif préexistant `test_model_tags_consistency.py`, non lié) / 40 skipped / 1 xfailed**, ruff clean | ✅ |

**Preuve D4** :
```
RED  : import jarvis (uvicorn absent)      → ModuleNotFoundError: No module named 'uvicorn'
GREEN: import jarvis (uvicorn absent)      → OK, aucune exception, aucun bootstrap déclenché
GREEN: bootstrap_dependencies (même py)    → os.execv non appelé
GREEN: bootstrap_dependencies (autre py)   → os.execv appelé avec le bon interpréteur
GREEN: to_step_logger(logger)(step,msg,ok) → callable, délègue correctement à logger.info/error
Suite complète : 882 passed, 40 skipped, 1 xfailed, 1 failed (préexistant, hors périmètre)
```

**Leçons apprises (W-DEPLOY-4)** :
- Le fix appliqué lors d'une session précédente n'avait **jamais été committé/poussé**
  (resté dans un bac à sable local disparu entre deux conversations) — le dépôt
  GitHub était toujours dans l'état buggé au moment du clonage pour cette session.
  Rappel : un correctif n'existe que s'il est committé ; « ça marchait dans une
  session précédente » n'est pas une preuve de livraison.
- `jarvis.py` porte le titre « Composition Root » dans son propre docstring — le
  premier patch (non retenu) violait ce principe en logeant la logique de bootstrap
  directement dedans. Le refacto final respecte SRP : `log_adapter.py` (adaptation),
  `dependency_bootstrap.py` (orchestration provisioning + relance), `jarvis.py`
  (assemblage pur, zéro logique propre au-delà du séquencement des appels).
- Bug D4.2 illustre l'intérêt de centraliser l'adaptation logger→callback en un seul
  module (`log_adapter.py`) plutôt que de la dupliquer à chaque site d'appel :
  un seul endroit à corriger pour les deux call-sites (`ensure_venv`,
  `ensure_ollama_binary`).

**Fichiers livrés (session, non encore commités)** : `jarvis.py` (modifié),
`services/log_adapter.py` (nouveau), `services/dependency_bootstrap.py` (nouveau).

**Prochaine micro-tâche** : `git add` + commit + push, puis relancer
`launchers\JARVIS.bat` sur H:\Projet-JARVIS pour confirmer en conditions réelles
que `bootstrap_dependencies()` installe bien fastapi/uvicorn/etc. dans
`portable_python\win\` et que JARVIS démarre jusqu'à `http://localhost:8000`.
Corriger ensuite D4.2 (`Logger` non-callable dans `ensure_ollama_binary`) si un
déploiement sans binaire Ollama pré-livré est un scénario à couvrir.

---

## 🔧 W-DEPLOY-5 — `ModuleNotFoundError: uvicorn` persistant malgré install "OK" — 07/08/2026

> Suite directe de W-DEPLOY-4. Rejeu réel sur H:\Projet-JARVIS avec le refacto SRP
> en place : `bootstrap_dependencies()` tourne, log "[Setup] OK" après ~67s
> d'installation pip réussie — mais `import uvicorn` échoue quand même juste
> après, dans le même process. Cause racine différente de W-DEPLOY-4 : le
> `._pth` de la distribution Python embeddable désactive `site-packages`.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| D5.1 | **Bug réel (E2E)** : `logs\jarvis_core.log` → `ModuleNotFoundError: No module named 'uvicorn'` sur `jarvis.py:95` (`import uvicorn`), **après** un log `[Setup] OK` de `bootstrap_dependencies()` confirmant une installation pip réussie (67s, "pip mis à jour avec succès" + "OK") | ✅ reproduit en réel |
| D5.2 | **Diagnostic** : `portable_python\win\` est une distribution Python **embeddable** officielle (`scripts/install_portable_python.py` télécharge `python-3.12.10-embed-amd64.zip`). Ces distributions livrent un fichier `pythonXXX._pth` qui désactive `site` par défaut → `Lib\site-packages` n'est **jamais** ajouté à `sys.path`, même après un `pip install` réussi. Le projet avait déjà une fonction pour patcher ce fichier (`enable_site_packages` dans `install_portable_python.py`), mais elle n'est appelée que lors d'une installation manuelle via ce script — jamais par `ensure_venv()` au démarrage normal de `jarvis.py` | ✅ cause racine identifiée |
| D5.3 | **RED** : reproduction fidèle — dossier "embeddable" factice avec `._pth` contenant `#import site` (commenté) → `is_site_enabled()` retourne `False`, confirmant que le scénario réel est bien reproduit avant correctif | ✅ |
| D5.4 | **GREEN — nouveau module SRP** : `services/embeddable_python.py` (responsabilité unique : lire/patcher le `._pth` — `is_site_enabled()`, `enable_site_packages()`, idempotents, ne connaissent rien de venv/pip/du cycle de vie du process) | ✅ |
| D5.5 | **GREEN — intégration** : `services/system.py::ensure_venv()` appelle `enable_site_packages()` avant toute installation quand l'interpréteur est portable/embeddable ; **changement de signature** — retourne désormais `tuple[str, bool]` (`python_path`, `restart_required`) au lieu d'un simple `str`, car un `._pth` fraîchement patché n'est relu qu'au **redémarrage** de l'interpréteur (patcher le fichier sur disque ne change rien au `sys.path` du process déjà en cours) | ✅ |
| D5.6 | **GREEN — propagation** : `services/dependency_bootstrap.py::bootstrap_dependencies()` déclenche désormais la relance (`os.execv`) sur `restart_required OR chemin différent` — auparavant seule la différence de chemin déclenchait une relance, ce qui ratait exactement le cas embeddable (même chemin, mais redémarrage quand même nécessaire) | ✅ |
| D5.7 | **VERIFY** : `import jarvis` toujours safe ; preuve intégrée — `ensure_venv()` mocké avec `._pth` désactivé → retourne bien `restart_required=True` et log "site-packages activé (._pth corrigé) — redémarrage requis" ; `bootstrap_dependencies()` mocké sur les 3 scénarios (même interpréteur sans patch → pas de relance ; interpréteur différent → relance ; même interpréteur mais `restart_required=True` → relance quand même) → passent ; suite complète → **892 passed / 1 failed (même faux positif préexistant) / 40 skipped / 1 xfailed** (vs 882 avant, +10 tests), ruff clean | ✅ |

**Preuve D5** :
```
RED  : is_site_enabled(embeddable factice, #import site) → False (reproduit le bug)
GREEN: enable_site_packages(...)                          → True, "#import site" → "import site"
GREEN: is_site_enabled(...) après patch                   → True
GREEN: ensure_venv() avec ._pth désactivé (mocké)          → (python_path, restart_required=True)
GREEN: bootstrap_dependencies() avec restart_required=True → os.execv appelé (même si même chemin)
GREEN: bootstrap_dependencies() cas nominal (déjà activé)  → os.execv non appelé
Suite complète : 892 passed, 40 skipped, 1 xfailed, 1 failed (préexistant, hors périmètre), ruff clean
```

**Leçons apprises (W-DEPLOY-5)** :
- Un `pip install` qui retourne `returncode == 0` ("OK" dans les logs) ne garantit
  **pas** que les paquets installés seront importables dans le process appelant —
  piège classique des distributions embeddable Windows, invisible dans n'importe
  quel test qui ne recrée pas un vrai fichier `._pth` désactivé.
- Le projet avait déjà la bonne fonction (`enable_site_packages` dans
  `scripts/install_portable_python.py`) mais elle n'était câblée que sur le chemin
  d'installation manuelle, jamais sur le chemin de démarrage normal
  (`jarvis.py` → `ensure_venv()`). Une fonction correcte mais non appelée au bon
  endroit produit exactement le même symptôme qu'une fonction absente.
- Un fichier `._pth` n'est lu **qu'au démarrage** de l'interpréteur embeddable — le
  patcher sur disque en cours d'exécution ne change rien au `sys.path` déjà résolu
  du process courant. D'où la nécessité d'élargir la condition de relance dans
  `dependency_bootstrap.py` : chemin différent **OU** drapeau explicite
  `restart_required`, sans quoi ce cas précis (même interpréteur, mais tout juste
  patché) ne redémarre jamais et le `ModuleNotFoundError` persiste malgré le "OK".

**Fichiers livrés (session, non encore commités)** : `services/embeddable_python.py`
(nouveau), `services/system.py` (modifié — signature `ensure_venv` changée),
`services/dependency_bootstrap.py` (modifié), `tests/test_embeddable_python.py`
(nouveau, 7 tests), `tests/test_dependency_bootstrap.py` (nouveau, 3 tests).

**Prochaine micro-tâche** : `git add` + commit + push, puis relancer
`launchers\JARVIS.bat` sur H:\Projet-JARVIS. Attendu cette fois : le premier
lancement patche le `._pth`, log "redémarrage requis", se relance automatiquement
(transparent pour l'utilisateur), et JARVIS démarre jusqu'à `http://localhost:8000`.
Si un `ModuleNotFoundError` persistait malgré tout, vérifier manuellement le
contenu de `portable_python\win\python312._pth` sur la clé pour confirmer que le
patch a bien été écrit sur disque (droits d'écriture sur la clé USB à vérifier).

---

## 🔧 W-DEPLOY-6 — 400 Bad Request sur `/api/generate` (question posée via l'UI web) — 07/08/2026

> Suite directe de W-DEPLOY-5 : JARVIS démarre enfin jusqu'à `http://localhost:8000`
> (fix `._pth` confirmé fonctionnel). Première question posée via l'interface web
> → `"Une erreur est survenue : Ollama echec apres 3 tentative(s) ... 400 Bad
> Request"`. Deux bugs réels empilés, retrouvés via `logs\ollama.log` (GIN 400 sur
> `/api/generate`, juste après un `/api/embed` réussi) + `curl /api/tags`.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| D6.1 | **Bug réel #1 (root cause)** : `services/pipeline_steps.py::select_model()` appelle `provider.resolve_model(agent_key)` — passe la **clé d'agent** ("techlead", "dev", "network"...) là où `resolve_model()` attend un **nom de modèle**. Aucune clé d'agent ne matche jamais un tag Ollama → le fallback `first_available()` est systématiquement atteint, pour n'importe quel agent | ✅ reproduit (RED) |
| D6.2 | **Bug réel #2 (aggravant)** : `services/adapters/ollama_adapter.py::first_available()` renvoyait `models[0]` sans filtrer par capacité. Sur cette clé, `/api/tags` liste `hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M` (capability `["embedding"]` seulement) en premier — c'est le modèle **le plus récemment pull**, Ollama semble trier par `modified_at` décroissant. Résultat : le fallback renvoyait un modèle embedding-only à `/api/generate`, qu'Ollama rejette légitimement en 400 | ✅ reproduit (RED) |
| D6.3 | **Découverte annexe (non exploitée, hors périmètre)** : `config/__init__.py::get_agent_profiles()` attend `agent_profiles.json` sous forme de **liste** avec un champ `"key"` par profil, alors que le fichier réel est un **dict** `{"profiles": {"<key>": {...}}}` (même format que celui déjà lu correctement par `agents/base.py::_load_profile`). Cette fonction planterait si elle était appelée — mais elle est **dead code**, jamais invoquée en production (vérifié par grep exhaustif). Non corrigée cette session (pas sur le chemin du bug réel) | ⚠️ notée, non corrigée |
| D6.4 | **RED** : reproduction fidèle — `select_model("techlead", None, provider_mock)` avec `resolve_model` échouant toujours (comme sur la clé) → renvoie bien le modèle embedding, confirmant D6.1 ; `first_available()` avec `/api/tags` mocké dans l'ordre observé sur la clé (embedding en premier) → renvoie bien le modèle embedding, confirmant D6.2 | ✅ |
| D6.5 | **GREEN — nouveau module** : `config/agent_profiles.py` (`model_for_agent(agent_key)`, responsabilité unique : lire le `"model"` configuré pour un agent dans `agent_profiles.json`, dégradation gracieuse si fichier absent/corrompu — ne duplique pas le cache mtime riche de `agents/base.py::_load_profile`, juste l'accès minimal nécessaire aux appelants sans instance `BaseAgent`) | ✅ |
| D6.6 | **GREEN — fix D6.1** : `select_model()` résout désormais `model_for_agent(agent_key)` puis `provider.resolve_model(<modèle configuré>)`, au lieu de `resolve_model(agent_key)` directement | ✅ |
| D6.7 | **GREEN — fix D6.2** : `OllamaAdapter` gagne `_fetch_models_raw()` (cache 30s partagé, dicts complets avec `capabilities`) ; `_fetch_models()` en dérive les noms (comportement externe inchangé) ; `first_available()` filtre désormais sur la capability `"completion"` (ou absence du champ `capabilities`, pour compat avec anciennes versions d'Ollama), et saute tout modèle embedding-only | ✅ |
| D6.8 | **VERIFY** : `import jarvis` toujours safe ; 3 reproductions RED confirmées puis GREEN après fix (`select_model` via profil réel `techlead` → bon tag Qwen2.5, fallback jamais atteint ; `first_available` saute l'embedding, renvoie le premier modèle `completion` ; cas limites `first_available` : que des modèles embedding → `None` sans crash, champ `capabilities` absent → considéré disponible) ; 11 nouveaux tests (`test_agent_profiles_config.py` ×4, `TestSelectModel` ×4 dans `test_pipeline_steps.py`, `TestOllamaAdapter` ×3 dans `test_adapters.py`, 1 test existant adapté) ; suite complète → **903 passed / 1 failed (même faux positif préexistant) / 40 skipped / 1 xfailed** (vs 892 avant, +11), ruff clean | ✅ |

**Preuve D6** :
```
RED  : select_model("techlead", None, provider) avec resolve_model(agent_key) qui échoue
       toujours -> "hf.co/nomic-ai/nomic-embed-text-v2-moe-GGUF:Q4_K_M" (bug confirmé)
GREEN: select_model("techlead", None, provider) avec le vrai agent_profiles.json
       -> "hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M", first_available() jamais appelé

RED  : first_available() avec /api/tags = [embedding, completion] (ordre observé sur la clé)
       -> renvoie le modèle embedding (bug confirmé)
GREEN: first_available() même liste -> saute l'embedding, renvoie le modèle completion
GREEN: first_available() que des modèles embedding -> None (pas de crash)
GREEN: first_available() sans champ 'capabilities' -> considéré disponible (backward compat)

Suite complète : 903 passed, 40 skipped, 1 xfailed, 1 failed (préexistant, hors périmètre), ruff clean
```

**Leçons apprises (W-DEPLOY-6)** :
- Deux bugs indépendants peuvent se **masquer l'un l'autre en apparence** : D6.1 seul
  aurait pu passer inaperçu si `first_available()` avait eu la bonne heuristique
  (n'importe quel modèle *completion* aurait alors été choisi par accident, et la
  requête aurait fonctionné malgré la mauvaise raison). C'est l'ordre de pull des 7
  modèles (embedding en dernier, donc trié en premier par Ollama) qui a rendu le
  bug D6.1 visible en le combinant à D6.2. Corriger uniquement le symptôme visible
  (D6.2) aurait laissé D6.1 dormant, prêt à ressurgir dès qu'un nouveau modèle
  embedding serait pull en dernier.
- `agent_profiles.json` a **deux lecteurs incompatibles** dans le code : le bon
  (`agents/base.py::_load_profile`, dict sous `"profiles"`) et un mort mais
  buggé (`config/__init__.py::get_agent_profiles()`, attend une liste). Un lecteur
  jamais appelé ne casse jamais rien en pratique — mais laisse un piège pour la
  prochaine personne qui l'utilisera en pensant qu'il est fonctionnel. À nettoyer
  ou corriger un jour (D6.3, hors périmètre de cette session).
- `first_available()` est un **fallback de dernier recours** : son contrat implicite
  ("un modèle qui marche pour générer du texte") n'était pas vérifié par le code,
  seulement par la chance de l'ordre des modèles installés. Un fallback doit
  respecter le même contrat que le chemin nominal, sinon il n'est fiable que par
  accident.

**Fichiers livrés (session, non encore commités)** : `config/agent_profiles.py`
(nouveau), `services/pipeline_steps.py` (modifié), `services/adapters/ollama_adapter.py`
(modifié), `tests/test_agent_profiles_config.py` (nouveau, 4 tests),
`tests/test_pipeline_steps.py` (modifié, +4 tests `TestSelectModel`),
`tests/test_adapters.py` (modifié, +3 tests, 1 adapté).

**Prochaine micro-tâche** : `git add` + commit + push (avec le fix `._pth` de
W-DEPLOY-5, toujours pas poussé à ce stade), puis relancer `launchers\JARVIS.bat`
et reposer une question via l'UI web. Attendu : la question est traitée par le
modèle configuré pour l'agent (Qwen2.5 pour techlead/orchestrateur/etc.), plus
d'erreur 400. Nettoyer D6.3 (`get_agent_profiles()` dead code buggé) dans une
session ultérieure si cette fonction doit un jour être utilisée.

---

## 🔧 POST-DEPLOY-AUDIT — Clé USB (07/08/2026)

> Audit rapide post-déploiement clé USB : fix vision OK, consentement décoratif, fixture coûteuse, mémoire hypothétique.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| AUDIT.1 | **Consentement diagnostic_ext — endpoint réel** : ajouter `POST /api/diagnostic/consent` → `DiagnosticExtService.grant_consent()` (services/diagnostic_ext/service.py:72). Le fichier `.diagnostic_consent` devient mécanisme d'urgence seulement. Documenter que `ensure_consent()` n'est pas un vrai contrôle d'accès (gate décoratif : `os.path.exists` contournable en 1 ligne). | ✅ livré (F-DIAG-1, 07/08/2026) |
| AUDIT.2 | **Fixture `_restore_ctx` — teardown sans side-effects réseau** : `tests/test_api.py:121-125` appelle `ctx._ctx.initialize()` qui instancie `InferenceService` (tente Ollama 11436), `VectorService`, etc. Remplacer par `AppContext()` vierge sans `_do_initialize()` ou supprimer le rappel (mocks réappliqués au setup suivant via `autouse`). Objectif : tests rapides, déterministes, sans dépendance machine. | ⏳ TODO |
| AUDIT.3 | **Mémoire vectorielle polluée — documentation hypothèse** : taille 39 KB `vector_index.json` corrélée à "réponse d'hier" = hypothèse sans test de régression (contaminé → nettoyé → non contaminé). Noter comme "nettoyage empirique acceptable en dépannage" — **ne pas classer root cause confirmée** sans repro. Si récurrence → ajouter test d'intégration `test_vector_index_isolation`. | 📝 NOTÉ |

**Preuve vision** (déjà livré) :
```
controllers/routes/agents.py:142 → strip_data_uri(image) appelé avant vision_agent.run()
tests/test_api.py:244-272 → test_vision_strips_data_uri_prefix_before_agent (spy valide)
```

---

## 🔧 F-DIAG — Frontend diagnostic étendu : consent API + boutons witr/psinfo (07/08/2026)

> Décision design (senior) : **pas d'endpoint d'exécution direct** pour witr — les
> boutons de l'onglet Outils pré-remplissent le chat (réutilise Toolbox/agent existant,
> KISS). Le consentement devient un vrai point d'entrée API (AUDIT.1) avec toggle UI.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| F1.1 | **RED** : 4 tests consent API (`tests/test_api.py::TestDiagnosticConsent`) — GET état absent → False ; POST true → fichier créé + True ; POST false → fichier supprimé + False ; body vide → 422. Service monkeypatché vers tmpdir (jamais `config/.diagnostic_consent`) | ✅ |
| F1.2 | **GREEN** : `services/diagnostic_ext/service.py` → `revoke_consent()` (suppression fichier, FileNotFoundError toléré, audit log) ; `models/schemas.py` → `ConsentRequest(consent: bool)` ; `controllers/routes/diagnostic_ext.py` (GET état via `ensure_consent()`, POST grant/revoke, réponse = état réel après opération, 500 si échec) ; monté dans `controllers/router.py` | ✅ |
| F1.3 | **Frontend toggle** : `static/index.html` → groupe Settings « Diagnostic externe » (toggle `.toggle` existant + `#consent-status`) ; `static/assets/js/app.js` → `restoreConsentState()`, `setConsentStatus()`, handler POST change ; appelé au boot | ✅ |
| F2.1 | **Boutons Outils** : `refreshTools()` → barre `.tools-actions` avec « 🔍 Analyser un processus (witr) » (prompt nom/port → `pourquoi le processus X tourne`) + « 📊 État système détaillé (psinfo) » (→ `état détaillé du système`) ; `switchToChat(text)` bascule sur l'onglet chat + pré-remplit + focus | ✅ |
| F2.2 | **Fix bug rendu `[object Object]`** : BINARIES/NETWORK.ports affichés « [object Object] » → pretty-print JSON des valeurs objets/tableaux (`typeof === 'object'`) | ✅ |
| F3.1 | **CSS** : `.tools-actions`, `.tool-action-btn`, `.tools-actions-hint`, `.consent-status`/`.consent-ok`/`.consent-warn` (style.css, cohérent avec design system existant) | ✅ |
| F3.2 | **README** : section « Outils de diagnostic étendu » (tableau outils/déclencheurs, prérequis consentement + binaires, distinction onglet Outils vs chat) + note sur l'onglet Outils | ✅ |
| F3.3 | **VERIFY** : `pytest tests/test_api.py` → vert (consent + suite) ; `ruff check` ; suite complète sans régression | ✅ |

---

## 🔧 V-SWITCH — Vision : bascule Llama-3.2-11B-Vision → moondream (08/08/2026)

> Bug réel (déploiement clé USB) : `ollama pull` + `/api/vision` →
> `"'llama3.2-vision' is no longer compatible with your version of Ollama...` (500
> côté API). Le HF import leafspark était devenu incompatible avec la version
> d'Ollama embarquée. Décision : bascule sur **moondream** (1,8B, ~1,4 Go, CPU-only,
> suffisant pour description d'image / OCR basique).

| # | Micro-tâche | Statut |
|---|-------------|--------|
| V1.1 | `services/selector.py` : `VISION_MODELS = ["moondream"]` (fallback `fallback_models()` mis à jour par dérivation) | ✅ |
| V1.2 | `config/model_sizes.json` : entrée `moondream` (ram 2 Go, vram 0, disk 1.4 Go, cpu_only, vision) — leafspark retiré | ✅ |
| V1.3 | `README.md` (3 blocs, tableaux modèles, feature vision) + `AGENTS.md` + `.opencode/AGENTS.md` + `models/ollama/MODELS.md` + `ports/__init__.py` + `static/assets/js/app.js` (message erreur) → moondream | ✅ |
| V1.4 | Tests : `tests/conftest.py` FakeInferenceService + `tests/test_model_llama_vision.py` → `moondream` ; `pytest test_selector + test_model_tags_consistency + test_api` → 58 passed / 1 skipped (live) ; ruff clean | ✅ |

**Commande utilisateur (pull le modèle)** :
```
.\bin\ollama.exe pull moondream
.\bin\ollama.exe rm hf.co/leafspark/Llama-3.2-11B-Vision-Instruct-GGUF:Q4_K_M
```

---

## 🧰 P-PORTABLE — Ollama 100 % portable : install.py pose le binaire SUR LA CLÉ (08/08/2026)

> Contexte : l'Ollama **système** a été désinstallé du PC de déploiement
> (`shutil.which("ollama")` ne retourne plus rien). Le README et `scripts/install.py`
> renvoyaient encore vers des installations **système** (PowerShell administrateur
> `irm https://ollama.com/install.ps1 | iex` sous Windows, `curl ... | sh` sous
> Linux/macOS). Or les machines à auditer ne sont jamais le poste de déploiement de
> la clé : installer Ollama sur le poste client n'a aucun intérêt. Décision :
> `scripts/install.py` pose le binaire **portable** dans `bin\` (+ `lib\ollama\`),
> réutilisant les installers déjà validés de `services/ollama_installer.py` ;
> `JARVIS.bat` garde le filet de sécurité (re-téléchargement au 1er lancement via
> `ensure_ollama_binary`).

| # | Micro-tâche | Statut |
|---|-------------|--------|
| P1.1 | **RED** : `test_install_final_message.py` conservé (2 tests `print_final` — pas de `bin\ollama.exe serve` quand aucun binaire portable, présent quand binaire fourni) | ✅ |
| P1.2 | **GREEN** : `scripts/install.py::setup_ollama()` réécrit — binaire portable déjà présent sur la clé → OK ; sinon invitation « Installer Ollama portable sur la cle ? [y/N] » → branche Windows `_install_windows_zip()` / Linux `_install_linux_tar()` / macOS brew+script (non-packagé) ; plus aucun `shutil.which("ollama")` système, plus aucun `irm`/`install.sh` ; aucun échec si utilisateur répond N (JARVIS.bat téléchargera) | ✅ |
| P1.3 | **GREEN** : `print_final()` — sans binaire portable : « (auto — téléchargé au 1er lancement de launchers\JARVIS.bat, jamais sur l'ordi) » au lieu de « ollama serve (installation système détectée) » ; avec binaire : « bin\ollama.exe serve (portable, sur la cle) » | ✅ |
| P1.4 | **GREEN** : `import shutil` retiré de install.py (devenu inutile) | ✅ |
| P2.1 | **README** : Étape 3 renommée « Installer les dépendances Python et Ollama portable (sur la clé) » + note 🟢 « rien n'est installé sur l'ordinateur — machines à auditer ≠ poste de déploiement » ; Étape 4 : note `bin\ollama.exe absent ?` → renvoie à l'étape 3 (et JARVIS.bat en filet) ; tableau « pour les curieux » : install.py télécharge Ollama portable, launchers le re-téléchargent s'il manque | ✅ |
| P3.1 | **VERIFY** : `pytest tests/test_install_final_message.py -q` → 2 passed ; `pytest tests/test_api.py -q` → 48 passed ; `ruff check scripts/install.py tests/test_install_final_message.py` → clean | ✅ |
| P3.2 | **Commit + push** : `fix(install): setup_ollama 100% portable — binaire posé sur la clé, jamais d'install système (irm/install.sh supprimés)` | ✅ |
---

## P-REPAIR — lib\ollama\ réparé : distribution complète v0.30.10 (08/08/2026)

> Contexte : l'audit lecture seule a révélé que `lib\ollama\` ne contenait que
> `cuda_v12\` (5 DLL). Tous les fichiers critiques manquaient (libmtmd.dll,
> llama-server.exe, ggml-base.dll, ggml-cpu-*.dll, libllama.dll) — la clé n'était
> PAS fonctionnelle offline. Réparation : téléchargement v0.30.10 complet
> (1 393,9 Mo), extraction temp, remplacement intégral de `lib\ollama\`
> (robocopy /E /XO : 48 fichiers copiés / 18 identiques sautés / 0 échec).

| # | Micro-tâche | Statut |
|---|-------------|--------|
| P-R.1 | **Audit** : bin\ollama.exe présent (35,7 Mo, SHA256 e44b55b3f10310663ac058d82d0ee18eb2bee6b20ccd0e8d992b48095961d225) ; lib\ollama\ incomplet ; CUDA v13 absent ; 24 blobs = 28,66 Go ; 7 manifests indexés ; .env OK (host/modèles posés par launchers) | ✅ |
| P-R.2 | **Téléchargement** : zip v0.30.10 complet (1 393,9 Mo) extrait — llama-server.exe, libmtmd.dll, ggml-base.dll, libllama.dll, libllama-common.dll, ggml.dll + cuda_v12/cuda_v13/vulkan présents | ✅ |
| P-R.3 | **Copie** : nettoyage puis copie (2 interruptions par timeout shell sur clé USB) ; reprise robocopy : 48 copiés (110 Mo) + 18 sautés (identique 1 681 Mo) ; total clé : 66 fichiers / 1 833 Mo | ✅ |
| P-R.4 | **VERIFY réel** : `ollama serve` → `/api/version` → `{"version":"0.30.10"}` ; `ollama list` → 7 modèles indexés ; inference Qwen2.5-7B « test » → réponse générée (le NativeCommandError PowerShell est un artefact stderr spinner) | ✅ |
| P-R.5 | **Nettoyage** : %TEMP%\ollama-full.zip + extraction supprimés ; log serve conservés (ollama-serve.log/.err.log racine) | ✅ |

Leçons apprises (P-R) :
- Le zip v0.30.10 ne contient plus ollama.dll : la distribution est restructurée
  (libmtmd.dll, libllama.dll, libllama-common.dll, libllama-server-impl.dll,
  ggml*.dll) — ces fichiers dans lib\ollama\ sont les composants critiques.
- PowerShell Copy-Item sur clé USB peut dépasser 10 min : privilégier robocopy
  pour tout remplacement de masse > 1 Go (reprise sûre, skip des identiques).
- Un lib\ollama\ partiel (copie tuée par timeout) ne suffit pas : vérifier la
  présence des 3 dossiers (cuda_v12, cuda_v13, vulkan) + DLL racine après toute
  copie interrompue.

**Prochaine micro-tâche** : tester JARVIS.bat de bout en bout sur la clé (launchers
→ .env → serve → agents), puis suite pytest sur clé.
---

## W-TIMEOUT — OllamaAdapter : timeout httpx aligné sur le timeout modèle (08/08/2026)

> Contexte : premier usage réel en chat navigateur → « Ollama echec apres 3
> tentative(s) sur http://127.0.0.1:11436/api/generate: Server error » (7 erreurs
> critiques dans la console). Diagnostic : le client httpx était créé avec un
> timeout FIXE de 30 s (`httpx.Timeout(30.0, connect=1.0)` en `__init__` et
> `_get_http()`) alors que la logique de retry attend jusqu'à 120 s
> (`_load_timeout()`, `config/model_preferences.json` — fichier absent → fallback
> 120). Le chargement à froid du modèle (4,7 Go Qwen2.5-7B depuis la clé USB)
> dépasse 30 s (32 s mesurés à 02:44, 23 s de cold load) → chaque tentative
> timeout avant d'arriver au retry.

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T1.1 | **RED** : chat navigateur 1er message → « Ollama echec apres 3 tentative(s) sur /api/generate: Server error » ; preuve logs : `[WARNING] SLOW ENDPOINT /api/jarvis - 32.125s` puis erreurs 500 console ×7 | ✅ |
| T1.2 | **GREEN** : `ollama_adapter.py` — timeout du client httpx aligné sur le timeout modèle : `httpx.Timeout(self._load_timeout(), connect=1.0)` en `__init__` (déplacé après init de `self._timeout`) et en `_get_http()` | ✅ |
| T1.3 | **VERIFY** : `ruff check services/adapters/ollama_adapter.py` → All checks passed ; `pytest tests/test_adapters.py tests/test_integration_ollama.py tests/test_ollama_port_single_source.py` → 27 passed, 3 échecs **pré-existants** (vérifié par `git stash` + run : échecs identiques sans la modif — contrat `query()` retourne `str` vs `result.success` attendu par les tests et live 3.6 s) | ✅ |
| T1.4 | **DOCS** : README Limitations connues + note cold start 30 s–2 min (ne pas re-cliquer Envoyer, retry 3×/120 s) ; ROADMAP section PHASE 7 — Déploiement clé USB réel §7.1 | ✅ |

**Leçons apprises (T)** :
- Le timeout per-request (`t = httpx.Timeout(timeout, connect=1.0)`) était déjà
  correct dans `_call_with_retry` ; le bug était le timeout du CLIENT
  (`self._http`) appliqué aux appels qui ne passent pas par la retry ou par
  défaut, et l'incohérence des deux valeurs (30 s vs 120 s) qui rendait le
  premier appel à froid impossible.
- `model_preferences.json` est ABSENT du repo : le timeout 120 s vient du
  fallback — les tests qui chargent ce fichier loguent un warning, pas une faute.
- Les tests d'intégration `test_query_qwen`, `test_query_unknown_model_returns_fail`,
  `test_timeout_config_respected` sont en échec PRÉ-EXISTANT : ils testent
  `query()` (qui retourne `str`) comme un `Result` — à réécrire dans une
  micro-tâche dédiée (ne PAS corriger le code de production pour plaire aux tests).

**Prochaine micro-tâche** : réécrire les 3 tests d'intégration ci-dessus
(contrat `query()` → `str`, tester le timeout via `Adapter timeout param`),
puis relancer la suite complète sur la clé.


## 🔄 W-CLEAN — Session 08/08/2026 (08/08) : normalisation LF + compression BACKLOG + commit

> Suite de W-TIMEOUT. Clôture de la session : les docs réécrits par PowerShell en CRLF
> ont été re-normalisés en **LF** (standard du repo — autocrlf off), les BOM UTF-8
> introduits par l'éditeur retirés (README/ROADMAP), et le BACKLOG compressé
> (sessions closes 25-26/07 : 330 lignes → ~35 lignes de synthèse, détail dans git).

| # | Micro-tâche | Statut |
|---|-------------|--------|
| C.1 | Normalisation : `git diff --stat` → 4 fichiers, 89 insertions (adapter 8, README 3, ROADMAP 16, BACKLOG 62) — plus aucun bruit de fins de ligne | ✅ |
| C.2 | BOM UTF-8 retirés (README L1, ROADMAP L1) ; date ROADMAP corrigée en UTF-8 | ✅ |
| C.3 | Compression BACKLOG (voir §Historique compressé) ; header état réel actualisé | ✅ |
| C.4 | **VERIFY** : ruff check ollama_adapter.py → All checks passed ; pytest ciblé (adapters, intégration, port single source) → 27 passed / 3 échecs pré-existants | ✅ |
| C.5 | **COMMIT** : `fix(adapter): aligne le timeout httpx sur le timeout modèle (cold start 30-120 s)` + docs + BACKLOG | ✅ |

**Leçons apprises (W-CLEAN)** :
- Le repo est en **LF** (`core.autocrlf=false`, fichiers committés en LF) : toute
  réécriture via PowerShell (`Set-Content`/`Out-File`) force le CRLF et noie le
  diff. Vérifier `git diff --stat` après chaque session docs ; re-normaliser en
  LF (`python -c` + `io.open(newline='')`) si nécessaire.
- L'éditeur en session précédente a aussi posé des **BOM UTF-8** (READER/ROADMAP)
  et cassé des caractères accentués (« � ») — relire `git diff` les lignes 1-5 de
  chaque fichier docs avant commit.

**Prochaine micro-tâche** : réécrire les 3 tests d'intégration (contrat `query()` → str) puis rejouer la suite complète sur la clé.

---

## 🧪 W-TES — Tests d'intégration Ollama : contrat `query()` → str (08/08/2026)

> Échecs PRÉ-EXISTANTS documentés en W-TIMEOUT (T1.3) : `test_query_qwen`,
> `test_query_unknown_model_returns_fail`, `test_timeout_config_respected`
> testaient `query()` (retourne `str`) comme un `Result`. Réécrits selon le
> contrat réel de `ollama_adapter.py` : `query()` → `str` pure, échec = levée
> `RuntimeError` (via `_call_with_retry`), timeout piloté par `_load_timeout()`
> (default 120 s — aucune modification de production, les tests sont mis au contrat).

| # | Micro-tâche | Statut |
|---|-------------|--------|
| T.1 | **RED (rejoué)** : `test_query_qwen` → `AttributeError: 'str' object has no attribute 'success'` ; `test_query_unknown_model_returns_fail` → `RuntimeError` non capté (404 réel) ; `test_timeout_config_respected` → même `AttributeError` | ✅ |
| T.2 | **GREEN** `tests/test_integration_ollama.py` : `test_query_qwen` → assert `isinstance(str)` + non vide ; `test_query_unknown_model_raises` (renommé) → `pytest.raises(RuntimeError)` ; `test_timeout_config_respected` → `adapter._timeout = 0.01` → RuntimeError < 10 s (retries ≈ 3×(0,01 s + 1 s sleep)) ; `import time` remonté en tête de module | ✅ |
| T.3 | **VERIFY** : `pytest tests/test_integration_ollama.py` → **12 passed** ; `test_adapters + test_ollama_port_single_source` → **18 passed** (non-régression) ; `ruff` → 0 erreur | ✅ |
| T.4 | **BACKLOG** : trace W-TES ajoutée ; les 3 échecs pré-existants de la suite sont clos | ✅ |
| T.5 | **COMMIT** : `test(integration): aligne les tests Ollama sur le contrat query() -> str` | ✅ |

**Leçons apprises (W-TES)** :
- Ne jamais corriger le code de production pour satisfaire un test qui ne reflète
  pas le contrat : `query()` est une `str` pure par design ; la réécriture s'est
  faite du côté des tests. `chat()` reste le contrat `Result` (exceptions déjà
  embarquées — les deux contrats coexistent par choix d'API).
- Le timeout n'a pas de paramètre public sur `query()` : il est porté par
  `_load_timeout()` (fichier config → défaut 120) et appliqué au client
  (`self._http`) et par requête (`_call_with_retry`). Pour forcer un timeout
  court en test d'intégration : positionner `adapter._timeout` (attribut
  documenté à l'init), sans toucher au fichier de config réel.
- Cold start vs warm : après un 1er appel réussi (`keep_alive`), la réponse
  Qwen2.5-7B revient en < 1 s sur cette machine — le test de timeout 0,01 s reste
  déterministe (aucun serveur ne répond en 10 ms).

**Prochaine micro-tâche** : rejouer la suite complète `pytest tests/` sur la clé
(sous Windows réel) puis confirmer chat navigateur + `/api/status` en conditions
réelles.
