# Plan TDD Clean Code — CSP 'unsafe-inline' → Nonce

## Contexte
- **Problème** : CSP actuel utilise `'unsafe-inline'` pour `script-src` et `style-src` (controllers/middlewares.py:129-130)
- **Risque** : Vulnérabilité XSS théorique via injection de scripts/styles inline
- **Cause** : 14 occurrences d'inline styles/onclick dans `static/assets/js/app.js` + 4 dans `static/index.html`
- **Solution** : Générer un nonce cryptographique par requête, l'injecter dans le CSP header, et l'utiliser dans tous les éléments inline

## Architecture de la solution

```
┌─────────────────────────────────────────────────────────────────┐
│  Middleware CSP (controllers/middlewares.py)                    │
│  ├── Génère nonce = secrets.token_urlsafe(16) par requête      │
│  ├── Injecte dans response.headers["Content-Security-Policy"]  │
│  └── Met nonce dans request.state.csp_nonce pour les templates │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Templates / Réponses HTML                                      │
│  ├── index.html : utilise nonce pour elements inline            │
│  ├── app.js : utilise nonce pour createElement('script')       │
│  └── Styles inline → classes CSS ou nonce sur <style>          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Micro-tâches TDD (Red → Green → Refactor)

### Phase 1 : Middleware & Génération du Nonce
| MT | Description | Fichier | Test TDD (RED) |
|----|-------------|---------|----------------|
| 1.1 | Test : middleware génère nonce unique par requête | `tests/test_csp_nonce.py` | Vérifie que 2 requêtes ont des nonces différents |
| 1.2 | Middleware : générer nonce, l'injecter dans CSP header + request.state | `controllers/middlewares.py` | Implémenter génération nonce et injection header |
| 1.3 | Test : CSP header contient `nonce-{value}` sans `'unsafe-inline'` | `tests/test_csp_nonce.py` | Vérifie format CSP et absence de 'unsafe-inline' |

### Phase 2 : Traitement de index.html (4 inline styles)
| MT | Description | Fichier | Test TDD (RED) |
|----|-------------|---------|----------------|
| 2.1 | Test : index.html servi avec éléments sans inline styles | `tests/test_csp_nonce.py` | Vérifie absence de `style="display:none"` |
| 2.2 | Refactor index.html : remplacer styles inline par classes CSS | `static/index.html` + `static/assets/css/style.css` | Utiliser classes utilitaires (ex: `.d-none`) |
| 2.3 | Test : éléments cachés toujours fonctionnels | `tests/test_csp_nonce.py` | Vérifie comportement identique |

### Phase 3 : Refactor app.js — Inline styles (7 occurrences)
| MT | Description | Fichier | Test TDD (RED) |
|----|-------------|---------|----------------|
| 3.1 | Test : innerHTML sans attributs `style=` | `tests/test_csp_nonce.py` | Vérifie absence de literaux `style="` dans JS généré |
| 3.2 | Créer classes CSS utilitaires pour styles fréquents | `static/assets/css/style.css` | Définir `.model-meta`, `.agent-btn-primary`, etc. |
| 3.3 | Refactor app.js : remplacer `style="..."` par `class="..."` | `static/assets/js/app.js` | Utiliser les nouvelles classes CSS |
| 3.4 | Test : rendu visuel identique | `tests/test_csp_nonce.py` | Comparaison de rendu ou test snapshot |

### Phase 4 : Refactor app.js — onclick handlers (4 occurrences)
| MT | Description | Fichier | Test TDD (RED) |
|----|-------------|---------|----------------|
| 4.1 | Test : aucun attribut `onclick=` dans HTML généré | `tests/test_csp_nonce.py` | Vérifie absence de `onclick=` dans JS |
| 4.2 | Refactor : deleguer events via `addEventListener` + `data-*` | `static/assets/js/app.js` | Utiliser event listeners sur containers parents |
| 4.3 | Test : fonctionnalité des boutons préservée | `tests/test_csp_nonce.py` | Simuler clicks et vérifier actions |

### Phase 5 : Intégration & Validation
| MT | Description | Fichier | Test TDD (GREEN/REFACTOR) |
|----|-------------|---------|----------------------------|
| 5.1 | Test E2E : page charge sans violation CSP | `tests/test_csp_nonce.py` | Utiliser check statique ou headless browser |
| 5.2 | Lint + full test suite (724 passed) | - | `ruff check . && pytest -q` |
| 5.3 | Mise à jour documentation | `fait.md`, `AUDIT_REPORT.md` | Documenter les changements CSP |

---

## Détails techniques par phase

### Phase 1 : Middleware Nonce
```python
# controllers/middlewares.py - Dans _security_headers_middleware
import secrets
from typing import Any

@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next):
    resp = await call_next(request)
    
    # Génération du nonce cryptographique
    nonce = secrets.token_urlsafe(16)
    request.state.csp_nonce = nonce  # Pour accès éventuel dans templates
    
    # Construction du CSP avec nonce
    csp = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'nonce-{nonce}'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "form-action 'self'"
    )
    resp.headers["Content-Security-Policy"] = csp
    # ... autres headers inchangés
    return resp
```

### Phase 2 : index.html
**Avant** :
```html
<img id="vision-preview" alt="Aperçu de l'image à analyser" style="display:none">
<div id="offline-banner" style="display:none"></div>
<button class="fb-back" id="fb-back" style="display:none" aria-label="Retour">←</button>
<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" id="image-input" style="display:none" aria-label="Sélection d'image cachée">
```

**Après** (ajout dans static/assets/css/style.css) :
```css
/* Classes utilitaires pour remplacer inline styles */
.d-none { display: none !important; }
```

**Dans index.html** :
```html
<img id="vision-preview" alt="Aperçu de l'image à analyser" class="d-none">
<div id="offline-banner" class="d-none"></div>
<button class="fb-back" id="fb-back" class="d-none" aria-label="Retour">←</button>
<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" id="image-input" class="d-none" aria-label="Sélection d'image cachée">
```

### Phase 3 : app.js — Styles inline
**Classes CSS à créer dans static/assets/css/style.css** :
```css
/* Styles fréquemment utilisés */
.model-meta { margin-bottom:6px; color:#aaa; font-size:11px; }
.agent-btn-primary { 
    width:100%; 
    background:#00d4ff; 
    color:#000; 
    border:none; 
    border-radius:6px; 
    padding:8px; 
    font-weight:700; 
    cursor:pointer; 
    font-size:12px;
}
.path-row { 
    display:flex; 
    justify-content:space-between; 
    align-items:center; 
    padding:4px 8px; 
    background:#1a1a24; 
    border-radius:4px;
}
.path-name { 
    color:#ccc; 
    font-family:monospace; 
    font-size:11px;
}
.revoke-btn { 
    padding:2px 8px; 
    background:#440000; 
    color:#ff4444; 
    border:none; 
    border-radius:4px; 
    cursor:pointer; 
    font-size:10px;
}
.error-label { color:#ff4444; }
.empty-paths { color:#555; }
```

**Refactor examples dans app.js** :
```javascript
// AVANT
result.innerHTML = '<div style="margin-bottom:6px;color:#aaa;font-size:11px;">Modele: ' + escHtml(data.model||'?') + '</div>' + renderMarkdown(data.response);

// APRES
result.innerHTML = '<div class="model-meta">Modele: ' + escHtml(data.model||'?') + '</div>' + renderMarkdown(data.response);

// AVANT
document.getElementById('analytics-kpis').innerHTML = `<div class="analytics-card"><div class="label" style="color:#ff4444;">Erreur chargement analytics : ${escHtml(e.message)}</div></div>`;

// APRES
document.getElementById('analytics-kpis').innerHTML = `<div class="analytics-card"><div class="label error-label">Erreur chargement analytics : ${escHtml(e.message)}</div></div>`;
```

### Phase 4 : app.js — onclick handlers
**Refactor de la délégation d'événements** :

Au lieu de :
```javascript
return `<div class="conv-item${active}" data-id="${c.id}" onclick="loadConv('${c.id}')">`;
<button class="conv-del" onclick="event.stopPropagation();deleteConv('${c.id}')" title="Supprimer">✕</button>;
```

Utiliser :
```javascript
// Dans la fonction qui génère la liste des conversations
return `<div class="conv-item${active}" data-conv-id="${c.id}">`;
<button class="conv-del" data-revoke-path="${btoa(p)}" title="Supprimer">✕</button>;

// Delegation d'événements (à placer dans l'initialisation ou un event listener global)
document.addEventListener('click', (e) => {
    // Gestion du chargement de conversation
    const convItem = e.target.closest('[data-conv-id]');
    if (convItem) {
        const convId = convItem.dataset.convId;
        loadConv(convId);
    }
    
    // Gestion du révocation de chemin
    const revokeBtn = e.target.closest('[data-revoke-path]');
    if (revokeBtn) {
        const encodedPath = revokeBtn.dataset.revokePath;
        revokePath(atob(encodedPath));
    }
});
```

**Dans les templates HTML générés** :
```javascript
// Pour les éléments de conversation
return `<div class="conv-item${active}" data-conv-id="${c.id}">`;
// Au lieu de onclick="loadConv('${c.id}')"

// Pour les boutons de révocation
<button class="conv-del" data-revoke-path="${btoa(p)}" title="Supprimer">✕</button>;
// Au lieu de onclick='revokePath(atob("${btoa(p)}"))'
```

---

## Tests TDD attendus

```python
# tests/test_csp_nonce.py
import re
from fastapi.testclient import TestClient
from controllers.router import app

client = TestClient(app)

def extract_nonce(csp_header: str) -> str:
    """Extrait la valeur du nonce du header CSP."""
    match = re.search(r"nonce-([^\s]+)", csp_header)
    return match.group(1) if match else ""

def test_csp_header_contains_nonce():
    resp = client.get("/")
    csp = resp.headers["Content-Security-Policy"]
    assert "nonce-" in csp
    assert "'unsafe-inline'" not in csp
    # Nonce doit changer à chaque requête
    nonce1 = extract_nonce(csp)
    resp2 = client.get("/")
    nonce2 = extract_nonce(resp2.headers["Content-Security-Policy"])
    assert nonce1 != nonce2, "Le nonce doit être unique par requête"

def test_index_html_no_inline_styles():
    resp = client.get("/")
    html_content = resp.text
    # Vérifier que les 4 styles inline sont remplacés
    assert 'style="display:none"' not in html_content
    # Vérifier la présence des classes de remplacement
    assert 'class="d-none"' in html_content or 'class="fb-back d-none"' in html_content

def test_app_js_generated_content_no_inline():
    # Simuler une requête qui génère du JS via app.js
    # Pour les éléments qui seraient générés par du JS côté client,
    # on vérifie que les templates dans app.js ne contiennent plus de styles/onclick inline
    js_content = open("static/assets/js/app.js", encoding="utf-8").read()
    # Les template strings ne doivent plus contenir style= ou onclick=
    assert 'style="' not in js_content or 'style="${"' in js_content  # Autoriser les template strings pour classes
    assert 'onclick=' not in js_content
    
    # Vérifier l'utilisation de classes et data-attributes
    assert 'class="model-meta"' in js_content
    assert 'data-conv-id=' in js_content
    assert 'data-revoke-path=' in js_content
```

---

## Questions de clarification

1. **Mécanisme d'injection du nonce dans index.html** :
   - Le projet sert actuellement `index.html` comme fichier statique. 
   - Options pour injecter le nonce :
     A) Convertir en template Jinja2 servi via endpoint FastAPI (recommandé pour sécurité maximale)
     B) Garder statique + ajouter un petit script inline au début qui définit une variable globale `window.CSP_NONCE` (à éviter car crée un petit unsafe-inline)
     C) Servir index.html via endpoint `/` qui injecte le nonce dans le template

   **Recommandation** : Option A pour éliminer complètement tout risque d'unsafe-inline, même minime.

2. **Éléments dynamiques dans index.html** :
   - Les 4 éléments avec `style="display:none"` sont-ils tous statiques ou certains sont affichés/cachés dynamiquement par JavaScript ?
   - Si dynamiques, la classe `.d-none` fonctionnera identique via `element.classList.toggle('d-none')`.

3. **Gestion des éléments créés dynamiquement** :
   - Pour les éléments créés via `document.createElement()` dans app.js, faudra-t-il définir le nonce ?
   - Réponse : Non, car ces éléments ne sont pas soumis au CSP s'ils ne contiennent pas de code inline. Seul le code inline dans les attributs HTML est concerné.

---

## Estimation temporelle

- **Phase 1 (Middleware)** : 30 min
- **Phase 2 (index.html)** : 20 min  
- **Phase 3 (app.js styles)** : 45 min
- **Phase 4 (app.js onclick)** : 45 min
- **Phase 5 (Tests + validation)** : 30 min
- **Total** : ~2h 50 min

---

# Plan TDD Solid Clean Code KISS — Optimisation Performance JARVIS (RTOC+CoT)

## Contexte & Décisions Architecturales

| Décision | Justification (Senior/KISS) |
|----------|----------------------------|
| **Mock Ollama** | Preprod = reproductible, CI-friendly, pas de flakiness |
| **Sync (pas async)** | USB 3.0 = goulot bus, pas CPU. Vectorization offline = pas d'attente user. Sync = debug simple, test trivial, pas d'event loop, pas d'`aiofiles`/`asyncpg` complexité. `orjson` + batch write + cache = gain réel sans complexité. |
| **Qualité > Vitesse** | Pipe déclenché manuellement, vectorization hors session chat. Fiabilité > micro-optimisation. |
| **64GB / USB 3.0** | Stockage borné → cache LRU borné, batch writes pour réduire write amplification sur clé USB. |

---

## Micro-Tâches RTOC (RED→GREEN→REFACTOR) — Ordre Validé

### Phase 0 — Outillage & Baseline (1h)

| MT | Description | Fichier | Critère RED |
|----|-------------|---------|-------------|
| 0.1 | `scripts/profile_app.py` : lance app mockée + `cProfile` sur endpoints réels | `scripts/profile_app.py` | Produit `profiles/baseline.prof` + top 10 `cumtime` |
| 0.2 | `scripts/bench_runner.py` : `BenchmarkRunner` (DI, `measure()`, `report()`) | `scripts/bench_runner.py` | Import OK, API stable |
| 0.3 | Lancer profilage app mockée → valider 3 cibles | - | Confirme : **Inference > Vector > I/O** |

> **Seuil entrée** : Seules fonctions > 5% temps total ou > 10ms/appel passent en Phase 1.

---

### Phase 1 — Goulet #1 : Inférence Ollama Mockée (Cible #1)

| MT | Description | Fichier | Critère RED |
|----|-------------|---------|-------------|
| 1.1 | `scripts/bench_inference.py` : 50 appels `inference.query()` mocké | `scripts/bench_inference.py` | Latence P95 > 50ms (overhead client HTTP) |
| 1.2 | **Optimisation 1** : `httpx.Client` singleton (connection pooling) au lieu recréation | `services/adapters/ollama_adapter.py` | GREEN: P95 ↓ 40% |
| 1.3 | **Optimisation 2** : Timeout adaptatif (exponentiel + jitter) config via `constants.py` | `services/adapters/ollama_adapter.py` | GREEN: pas de timeout fixe 120s |
| 1.4 | **Optimisation 3** : Retry seulement sur erreurs transitoires (5xx, timeout), pas 4xx | `services/adapters/ollama_adapter.py` | GREEN: pas de retry inutile |
| 1.5 | Tests régression + `pytest tests/test_inference.py -q` | - | GREEN |

> **Gain visé** : -40% latence overhead client HTTP (mock), reproductible.

---

### Phase 2 — Goulet #2 : Recherche Vectorielle (Cible #2)

| MT | Description | Fichier | Critère RED |
|----|-------------|---------|-------------|
| 2.1 | `scripts/bench_vector.py` : 100 requêtes `vector.search()` sur index 5k docs | `scripts/bench_vector.py` | P95 > 50ms (numpy O(N) naïf) |
| 2.2 | **Optimisation 1** : Embedding batch unique réutilisé (cache `query_vec`) | `services/vector.py` | GREEN: re-embedding éliminé |
| 2.3 | **Optimisation 2** : `numpy.dot` + `argsort` vectorisé (pas de loop Python) | `services/vector_search.py` | GREEN: O(N) vectorisé |
| 2.4 | **Optimisation 3** : Cache LRU borné (`MAX_VECTOR_CACHE=32`) + TTL config | `services/vector_cache.py` | GREEN: hit rate > 70% |
| 2.5 | Tests régression + `pytest tests/test_vector.py -q` | - | GREEN |

> **Gain visé** : -60% latence search (cache hit + vectorisation numpy).

---

### Phase 3 — Goulet #3 : I/O Fichiers Sync KISS (Cible #3)

| MT | Description | Fichier | Critère RED |
|----|-------------|---------|-------------|
| 3.1 | `scripts/bench_io.py` : 100 writes/reads conversations + memory (sync) | `scripts/bench_io.py` | P95 > 20ms (json stdlib + atomic write) |
| 3.2 | **Optimisation 1** : `orjson` (2-3x plus rapide, stdlib-compatible) | `services/file_utils.py` | GREEN: sérialisation ↓ 60% |
| 3.3 | **Optimisation 2** : Batch writes (accumulate + flush configurable) | `services/file_utils.py` | GREEN: syscalls ↓ 70% |
| 3.4 | **Optimisation 3** : Cache LRU mémoire pour reads fréquents (`memory.py`) | `services/memory.py` | GREEN: read hit > 80% |
| 3.5 | Tests régression + `pytest tests/test_conversation.py tests/test_memory.py -q` | - | GREEN |

> **Gain visé** : -50% latence I/O, write amplification réduite (clé USB 3.0).

---

### Phase 4 — Validation Globale & Rapport (30 min)

| MT | Description | Critère GREEN |
|----|-------------|---------------|
| 4.1 | Benchmark E2E : 10 conversations complètes (mock) | Latence E2E P95 < cible |
| 4.2 | Suite complète `pytest -q` | 724 passed, 0 failed |
| 4.3 | Générer `rapport_perf.md` (tableau avant/après 3 points) | Fichier créé, chiffres benchmarkés |
| 4.4 | Commit final `perf: optimize inference/vector/io (RTOC)` | Git clean |

---

### Rapport Final (`rapport_perf.md`)

```markdown
# Rapport Performance — JARVIS v5.4 (Preprod Mock)

## Méthodologie
- Profilage : `cProfile` sur app mockée (Ollama fake)
- Benchmarks : 50-100 itérations, P50/P95/P99, `statistics` stdlib
- TDD RTOC : RED (benchmark échoue cible) → GREEN (optimisation) → REFACTOR
- Sync KISS : pas d'async, USB 3.0 = goulot bus

## Résultats

| Point | Métrique | Avant | Après | Gain | Test |
|-------|----------|-------|-------|------|------|
| 1. Inférence (mock) | P95 overhead client | X ms | Y ms | -40% | GREEN |
| 2. Vector Search | P95 search 5k docs | X ms | Y ms | -60% | GREEN |
| 3. I/O Fichiers | P95 write+read | X ms | Y ms | -50% | GREEN |

## Preuves
- `profiles/baseline.prof` → `profiles/optimized.prof`
- Benchmarks reproductibles : `scripts/bench_*.py`
- Suite tests : 724 passed / 0 failed
```

---

### Guardrails Senior (Non-Négociables)

| Règle | Application |
|-------|-------------|
| **RED avant GREEN** | Benchmark écrit **avant** toute modif code |
| **Un fichier à la fois** | Jamais 2 optimisations en parallèle |
| **Rollback commit** | `git commit --allow-empty -m "perf: checkpoint phase N"` avant chaque phase |
| **Preuve > Supposition** | `py-spy record -o profile.svg -- python bench.py` pour chaque point |
| **Pas de `except: pass`** | Tous les `try` ont `_logger.warning/exception` |
| **Pas de magic numbers** | Seuils dans `config/constants.py` (`PERF_INFERENCE_P95_MS = 50`, etc.) |
| **KISS** | Sync, pas d'`aiofiles`/`asyncpg`, `orjson` + batch + cache LRU = tout |

---

### Fichiers Concernés

| Nouveau (créer) | Existant (modifier) |
|-----------------|-------------------|
| `scripts/profile_app.py` | `services/adapters/ollama_adapter.py` |
| `scripts/bench_runner.py` | `services/vector.py` / `vector_search.py` |
| `scripts/bench_inference.py` | `services/conversation.py` / `memory.py` |
| `scripts/bench_vector.py` | `services/file_utils.py` |
| `scripts/bench_io.py` | `config/constants.py` (seuils) |
| `profiles/` (dossier) | `rapport_perf.md` (généré) |

---

### Prêt à Lancer

**Ordre** : Phase 0 → 1 → 2 → 3 → 4 (validé)

**Prochaine action** : MT-0.1 (`scripts/profile_app.py`) — démarrage profilage.