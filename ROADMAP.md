# ROADMAP.md — Projet JARVIS
# Micro-tâches TDD — Une tâche = Un fichier = Un cycle RED/GREEN
# Mis à jour : 24 juillet 2026
# Règle : cocher [x] UNIQUEMENT après preuve verte collée.

---

## PHASE 1 — BLOQUANTS UTILISATEUR (priorité max)

### 1.1 Bouton "Envoyer" mort
- [x] **RED** : Ouvrir `http://localhost:8000`, taper un message, cliquer "Envoyer" → rien ne se passe.
- [x] **GREEN** : Ajouter `sendBtn.addEventListener('click', send);` dans `static/assets/js/app.js` (~ligne 199, après le listener Ctrl+Enter).
- [x] **PREUVE** : Clic sur "Envoyer" → message envoyé via POST /api/jarvis → réponse affichée.
- [x] **COMMIT** : `fix(ui): câble le bouton Envoyer au handler send()`

### 1.2 Création de conversation cassée (ok() wrapper)
- [x] **RED** : Envoyer un message (Ctrl+Enter) → console JS : `currentConvId` reste `null` → sidebar vide.
- [x] **GREEN** : Dans `app.js:637`, remplacer `cd.conversation_id` par `(cd.data || cd).conversation_id`.
- [x] **PREUVE** : Après 1er message, `currentConvId` ≠ null dans la console.
- [x] **COMMIT** : `fix(ui): déballe ok() sur la création de conversation`

### 1.3 Liste des conversations vide
- [x] **RED** : Recharger la page → sidebar "Conversations" affiche "Aucune conversation".
- [x] **GREEN** : Dans `app.js:513`, remplacer `data.conversations` par `(data.data || data).conversations`.
- [x] **PREUVE** : Les conversations existantes s'affichent dans la sidebar.
- [x] **COMMIT** : `fix(ui): déballe ok() sur la liste des conversations`

### 1.4 Chargement d'une conversation vide
- [x] **RED** : Cliquer sur une conversation dans la sidebar → le chat reste vide.
- [x] **GREEN** : Dans `app.js:549-554`, remplacer `conv.id` / `conv.messages` par `(conv.data || conv).id` / `(conv.data || conv).messages`.
- [x] **PREUVE** : Clic sur une conversation → les messages s'affichent dans le chat.
- [x] **COMMIT** : `fix(ui): déballe ok() sur le chargement de conversation`

### 1.5 Bouton "Appliquer" (Agents) — faux échec
- [x] **RED** : Onglet Agents → changer le modèle → cliquer "Appliquer" → toast rouge "Échec assignation: ?".
- [x] **GREEN** : Dans `app.js:314-316`, remplacer `res.status === 'ok'` par `res.data && !res.error`.
- [x] **PREUVE** : Clic "Appliquer" → toast vert "Modèle X assigné à Y".
- [x] **COMMIT** : `fix(ui): corrige le faux échec du bouton Appliquer (Agents)`

### 1.6 enhanceLastAssistant() cassé (feedback 👍👎)
- [x] **RED** : Envoyer un message → pas de boutons 👍👎 sous la réponse assistant.
- [x] **GREEN** : Dans `app.js:143-160`, remplacer `conv.messages` par `(conv.data || conv).messages`.
- [x] **PREUVE** : Après réponse assistant, les boutons 👍👎 et badges agent/modèle apparaissent.
- [x] **COMMIT** : `fix(ui): déballe ok() dans enhanceLastAssistant (feedback buttons)`

---

## PHASE 2 — BOUTONS FANTÔMES & ONGLETS MORTS

### 2.1 Bouton 📷 dans le chat — clic sans effet
- [x] **RED** : Cliquer sur 📷 dans la zone de saisie → rien.
- [x] **GREEN** : Dans `app.js`, ajouter :
  - `document.getElementById('vision-btn').addEventListener('click', () => document.getElementById('image-input').click());`
  - `document.getElementById('image-input').addEventListener('change', handleImageSelect);`
  - Fonction `handleImageSelect(e)` qui lit le fichier en base64 → stocke dans `pendingImage`.
  - Dans `send()`, inclure `image: pendingImage` dans le body si défini.
- [x] **PREUVE** : Clic 📷 → sélecteur fichier → image sélectionnée → envoyée avec le message.
- [x] **COMMIT** : `feat(ui): câble le bouton vision dans le chat`

### 2.2 Onglet Vision — clic sur la zone d'upload
- [x] **RED** : Onglet Vision → cliquer sur la zone "Cliquez ou déposez" → rien (seul drag&drop marche).
- [x] **GREEN** : Dans `app.js`, ajouter :
  - `document.getElementById('upload-zone').addEventListener('click', () => document.getElementById('vision-file').click());`
  - `document.getElementById('vision-file').addEventListener('change', handleVisionFile);`
- [x] **PREUVE** : Clic sur la zone → sélecteur fichier → image analysée.
- [x] **COMMIT** : `fix(ui): câble le clic sur la zone d'upload Vision`

### 2.3 Onglet Outils (🔧) — duplique Skills
- [x] **RED** : Cliquer sur l'onglet 🔧 Outils → affiche la grille Skills (doublon).
- [x] **GREEN** : Dans `app.js` :
  - Créer `async function refreshTools()` qui fetch `GET /api/diag` et remplit `#tab-tools .tools-grid`.
  - Dans le handler tab-switch (ligne ~45), remplacer `refreshSkills()` par `refreshTools()` quand `data-tab === 'tools'`.
- [x] **PREUVE** : Onglet Outils → affiche CPU, RAM, disque, réseau (pas les skills).
- [x] **COMMIT** : `feat(ui): câble l'onglet Outils sur /api/diag`

### 2.4 Sidebar Conversations — toggle + "Tout effacer"
- [x] **RED** : Le header de la sidebar ne toggle pas. Le bouton "Tout effacer" est invisible.
- [x] **GREEN** : Dans `app.js`, ajouter :
  - `document.getElementById('sidebar-convs-header').addEventListener('click', toggleConvs);`
  - `document.getElementById('clear-convs-btn').addEventListener('click', clearAllConvs);`
  - Retirer `style="display:none"` du bouton "Tout effacer" dans `index.html` (ou le rendre visible via JS).
- [x] **PREUVE** : Clic sur le header → la liste se masque/affiche. Clic "Tout effacer" → confirmation → conversations supprimées.
- [x] **COMMIT** : `fix(ui): câble le toggle sidebar et le bouton Tout effacer`

---

## PHASE 3 — PIPELINE RAG (Vector → Agent)

### 3.1 TypeError dans query_model() (2 args au lieu de 3)
- [x] **RED** : `pytest tests/test_wave_a.py::test_query_model_empty_task_sets_error -v` → échec ou `TypeError: run() missing 1 required positional argument: 'context'`.
- [x] **GREEN** : Dans `services/pipeline_steps.py:74-84`, corriger l'appel :
  ```python
  result = agent.run(prompt, model=model, context=state.get("context", {}))
  ```
- [x] **PREUVE** : `pytest tests/test_wave_a.py -q --timeout=30` → passed.
- [x] **COMMIT** : `fix(pipeline): passe context à agent.run() dans query_model`

### 3.2 Mismatch de clé vector_results vs similar_cases
- [x] **RED** : Test unitaire : `retrieve_context()` stocke dans `context["vector_results"]` mais `_similar_cases_block()` lit `context["similar_cases"]` → le bloc est toujours vide.
- [x] **GREEN** : Dans `services/pipeline_steps.py:47`, remplacer `context["vector_results"]` par `context["similar_cases"]`.
- [x] **PREUVE** : Test unitaire vert + `pytest tests/test_pipeline.py -q` → passed.
- [x] **COMMIT** : `fix(pipeline): aligne la clé similar_cases entre retrieve et agent`

### 3.3 Chemin vision — similar_cases hardcodé vide
- [x] **RED** : `pytest tests/test_orchestrator.py -q -k vision` → `similar_cases` toujours `[]`.
- [x] **GREEN** : Dans `services/orchestrator.py:152-155`, remplacer `"similar_cases": []` par un appel à `self.vector.search(task, top_k=3)` si `self.vector` est disponible.
- [x] **PREUVE** : Test vert + les résultats vectoriels apparaissent dans le contexte vision.
- [x] **COMMIT** : `feat(pipeline): peuple similar_cases dans le chemin vision`

---

## PHASE 4 — RÉGLAGES & STATUS BAR (mineur)

### 4.1 Modèle par défaut — persistance serveur
- [x] **RED** : Changer le modèle dans Réglages → recharger → le choix est perdu (localStorage only).
- [x] **GREEN** : Dans `app.js:825-827`, ajouter un `fetch('/api/settings', {method:'PUT', body: JSON.stringify({key:'default_model', value})})` après le `localStorage.setItem`.
- [x] **PREUVE** : Changer le modèle → recharger → le select affiche le bon modèle.
- [x] **COMMIT** : `fix(ui): persiste le modèle par défaut côté serveur`

### 4.2 Enter sur #fp-path non câblé
- [x] **RED** : Taper un chemin dans le champ → appuyer sur Enter → rien.
- [x] **GREEN** : Dans `app.js`, ajouter :
  ```javascript
  document.getElementById('fp-path').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') authorizePath();
  });
  ```
- [x] **PREUVE** : Taper un chemin + Enter → le dossier est autorisé.
- [x] **COMMIT** : `fix(ui): câble Enter sur le champ chemin des dossiers autorisés`

### 4.3 Status Bar — feedback d'erreur visible
- [x] **RED** : Arrêter le backend → la sidebar affiche `—` sans explication.
- [x] **GREEN** : Dans `app.js:481` et `489`, remplacer `catch(e) {}` par :
  ```javascript
  catch(e) {
    document.getElementById('st-backend').innerHTML = '<span class="status-dot dot-err"></span>HS';
  }
  ```
- [x] **PREUVE** : Backend arrêté → la sidebar affiche "HS" en rouge au lieu de `—`.
- [x] **COMMIT** : `fix(ui): affiche un feedback d'erreur dans la Status Bar`

---

## PHASE 5 — RACCOURCIS & EXTENSIONS (confort)

### 5.1 Ctrl+L — vider le chat
- [x] **RED** : Appuyer sur Ctrl+L → rien.
- [x] **GREEN** : Dans `app.js`, ajouter dans le listener `keydown` global :
  ```javascript
  if (e.ctrlKey && e.key === 'l') { e.preventDefault(); clearChat(); }
  ```
- [x] **PREUVE** : Ctrl+L → le chat se vide, `currentConvId = null`.
- [x] **COMMIT** : `feat(ui): câble Ctrl+L pour vider le chat`

### 5.2 Help box visible
- [x] **RED** : La help box est cachée (`display:none`), aucun moyen de l'afficher.
- [x] **GREEN** : Retirer `style="display:none"` de la `<details class="help-box">` dans `index.html`, ou ajouter un bouton `?` qui la toggle.
- [x] **PREUVE** : L'utilisateur peut voir les raccourcis documentés.
- [x] **COMMIT** : `fix(ui): rend la help box visible`

---

## PHASE 6 — PORTABILITÉ (chantier séparé, 🟠)

### 6.1 Linux — incohérence bin/ollama vs bin/linux/ollama
- [x] **RED** : Lancer `JARVIS.sh` → avertissement "binaire Ollama introuvable dans bin/linux/".
- [x] **GREEN** : Dans `services/ollama_installer.py:164`, remplacer `dest_bin = os.path.join(BIN_DIR, "ollama")` par `dest_bin = os.path.join(BIN_LINUX, "ollama")`.
- [x] **PREUVE** : `JARVIS.sh` ne logge plus l'avertissement.
- [x] **COMMIT** : `fix(portability): aligne le chemin d'install Ollama sur bin/linux/`

### 6.2 macOS — fallback explicite dans JARVIS.sh
- [x] **RED** : Sur macOS sans `bin/mac/ollama`, `JARVIS.sh` échoue silencieusement.
- [x] **GREEN** : Dans `launchers/JARVIS.sh:38`, ajouter un fallback :
  ```bash
  if [ ! -f "$OLLAMA_BIN" ]; then
    OLLAMA_BIN=$(which ollama 2>/dev/null)
  fi
  ```
- [x] **PREUVE** : Sur macOS avec Ollama système, JARVIS démarre sans erreur.
- [x] **COMMIT** : `fix(portability): fallback Ollama système dans JARVIS.sh (macOS)`

---

## RÈGLES DE VALIDATION (ne pas violer)

1. **UNE micro-tâche = UN fichier = UN cycle RED/GREEN.**
2. **Jamais deux fichiers dans le même commit.**
3. **Preuve verte collée AVANT de cocher [x].**
4. **Commit = point de retour sûr immédiat après le GREEN.**
5. **Ne PAS mélanger chantier UI (Phases 1-5) et chantier Portabilité (Phase 6).**
6. **Après tout collage de fichier Python : vider `__pycache__`.**
7. **Pour le wrapper ok() : stratégie unique = adapter le frontend (`(x.data || x)`). Ne PAS supprimer le wrapper backend.**

---

## ÉTAT DES LIEUX (référence)

| Composant | Statut | Bloquant ? |
|-----------|--------|------------|
| Bouton Envoyer | ✅ OK | — |
| Conversations (CRUD) | ✅ OK | — |
| Agents "Appliquer" | ✅ OK | — |
| enhanceLastAssistant | ✅ OK | — |
| Bouton 📷 chat | ✅ OK | — |
| Onglet Vision (clic) | ✅ OK | — |
| Onglet Outils | ✅ OK | — |
| Sidebar toggle/effacer | ✅ OK | — |
| Pipeline RAG | ✅ OK | — |
| Skills | ✅ Sain | — |
| Analytics | ✅ Sain | — |
| Réglages | ✅ OK | — |
| Toasts / Typing | ✅ Sain | — |
| Status Bar | ✅ OK | — |
| Linux | ✅ Fonctionnel | — |
| macOS | ✅ Portable | — |
