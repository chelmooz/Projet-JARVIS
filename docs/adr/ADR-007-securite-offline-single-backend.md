# ADR-007 : Sécurité du mode offline single-backend

**Statut :** Accepté
**Date :** 2026-07-20
**Décideur :** Data/Sécu/Docs + équipe JARVIS

## Contexte

JARVIS est un assistant mono-utilisateur, 100 % local, sans compte ni cloud
(threat model : machine cliente hors ligne, un seul utilisateur physique). Le
refactor T11 a supprimé le sélecteur de backend (`POST /api/backend/select`,
`select_backend`/`list_backends`) : **Ollama est le seul backend LLM**, assumé et
non sélectionnable.

## Décision

- Le backend est **fixe (Ollama)** ; aucune API de changement de backend n'est
  exposée. `GET /api/backend` retourne `{"backend": "ollama"}` à titre indicatif
  (statut, pas d'action).
- Les entrées utilisateur sensibles sont **sanitisées au bord du réseau** :
  `services/sanitize.py` (`safe_model_name`, `clean_text`, `safe_path_segment`,
  `validate_base64_image`, `scrub`) est appliqué dans les routes (`/api/agents/assign`
  via `safe_model_name`, vision via `validate_base64_image`), empêchant l'injection de
  noms de modèles/chemins arbitraires.
- Le CSP (`controllers/context.py`) autorise uniquement les ressources locales ;
  aucune dépendance CDN n'est chargée en production (chart.js est vendored localement
  — voir M6). `unsafe-inline` est évité pour réduire la surface XSS.

## Conséquences

- ✅ Surface d'attaque réduite : pas de bascule de backend arbitraire.
- ✅ Validation d'entrée centralisée et réutilisée (KISS, pas de patch ad hoc).
- ✅ Cohérent avec le modèle de menace mono-utilisateur offline.
- ⚠️ Pas de RBAC ni de HTTPS (limitation connue, documentée dans le README) :
  acceptable car usage local personnel uniquement.

## Modules impactés

- `controllers/routes/agents.py` — `safe_model_name` sur l'assignation de modèle.
- `models/schemas.py` — `AssignRequest` sans champ `backend` mort.
- `controllers/context.py` — CSP resserrée (M6).
- `services/sanitize.py` — utilitaires de validation.
