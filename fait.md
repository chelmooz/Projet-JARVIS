# CSP 'unsafe-inline' → Nonce Migration (Phase 1-4)

## Phase 1: Middleware & Tests (MT-1.1 → MT-1.5)
- [x] Middleware dans `controllers/middlewares.py` génère `secrets.token_urlsafe(16)` par requête
- [x] CSP header remplace `'unsafe-inline'` par `'nonce-{nonce}'`
- [x] Tests MT-1 à MT-5 : nonce présent, unique, format valide, plus d'unsafe-inline

## Phase 2: Index.html (MT-2.1 → MT-2.3)
- [x] 4 `style="display:none"` → `class="d-none"` dans `static/index.html`
- [x] Classe `.d-none` ajoutée dans `style.css`
- [x] Tests passent (MT-2.1: display:none absent, MT-2.2: d-none présent)

## Phase 3: app.js inline styles → CSS classes (MT-3.1 → MT-3.4)
- [x] `<div class="model-meta">` remplace `<div style="margin-bottom:6px;...">`
- [x] `<div class="mt-8">` remplace `<div style="margin-top:8px">`
- [x] `agent-btn-primary` class remplace le style inline du bouton agent
- [x] `error-label` class remplace `style="color:#ff4444;"` sur l'erreur analytics
- [x] `path-row` / `path-name` / `revoke-btn` / `empty-paths` classes remplacent les styles inline dans la liste des paths
- [x] Classes utilitaires ajoutées dans `style.css`
- [x] Aucun `style=` restant dans app.js
- [x] Tests MT-3.1, MT-3.4 passent

## Phase 4: app.js onclick → addEventListener délégation (MT-4.1 → MT-4.2)
- [x] `onclick="loadConv(...)"` → `data-conv-id` + délégation `document.addEventListener('click', ...)`
- [x] `onclick="event.stopPropagation();deleteConv(...)"` → `data-del-conv-id` + délégation
- [x] `onclick='revokePath(...)'` → `data-revoke-path` + délégation
- [x] Aucun `onclick=` restant dans app.js
- [x] Tests MT-4.1: onclick absent, MT-4.2: data-* attributs présents

## Tests
- 11/11 tests CSP passent
- 38 tests (CSP + router + cache) passent, aucune régression