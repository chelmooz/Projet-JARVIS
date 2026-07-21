---
name: audit-qualite
description: >
  Audit qualite mono-utilisateur complet en 123 items repartis sur 11 couches
  (API, stockage, hosting, config, cache, logs, stabilite...).
  Proprietaire: tech-lead. Reviewers obligatoires: devops-local, designer-qa, data-secu-docs.
---

# Audit Qualité Mono-Utilisateur — Skill JARVIS

## Propriété & Cycle d'Héritage

| Rôle | Agent | Responsabilité |
|------|-------|----------------|
| **Propriétaire principal** | `tech-lead` | Architecture, SOLID, dette technique, revue de code. Décide des merges. |
| **Co-propriétaire** | `devops-local` | Lanceurs, portabilité, scripts, monitoring, backups |
| **Auditeur officiel** | `designer-qa` | Tests, edge cases, vérification des ✅ / ⚠️ / ❌ |
| **Secrétaire** | `data-secu-docs` | ADR, CHANGELOG, .env.example, documentation |

**Cycle de modification :**
```
1. Tech Lead identifie une amélioration
2. Devops Local vérifie la portabilité
3. Designer QA écrit/révise les tests
4. Data/Secu/Docs met à jour doc + CHANGELOG
5. Tech Lead merge et met à jour la grille
```

## Grille d'Audit — 11 Couches, 123 Items

Chaque item attend une coche : ✅ OK · ⚠️ À améliorer · ❌ À corriger · N/A

---

### 1. Frontend — Agent : N/A (projet backend only)

*Projet API FastAPI — aucun composant frontend.*

---

### 2. APIs & Backend Logic — Agent : `tech-lead`

#### 2.1 Structure MVC
- [ ] Contrôleurs = délégation uniquement, pas de logique métier
- [ ] Un service = une responsabilité
- [ ] Modèles typés (dataclasses, Pydantic) — pas de `any`
- [ ] Middlewares nommés, responsabilité unique

#### 2.2 Design des Endpoints
- [ ] Verbes REST corrects (GET, POST, PUT, DELETE)
- [ ] Codes HTTP sémantiques (200, 201, 400, 404, 422, 500)
- [ ] Réponses JSON structurées `{ data, error }`
- [ ] Pagination sur les listes
- [ ] Pas de route orpheline

#### 2.3 Validation
- [ ] Validation sur chaque entrée utilisateur
- [ ] Messages explicites
- [ ] Valeurs par défaut pour optionnels

#### 2.4 Clean Code & SOLID
- [ ] Fonctions < 20 lignes, une responsabilité
- [ ] Nommage avec verbes d'action
- [ ] Pas de code mort
- [ ] Pas de `try/catch` vide ou silencieux
- [ ] Dépendances injectées (DIP)
- [ ] Commentaires en français sur chaque bloc

#### 2.5 Tests
- [ ] Tests unitaires sur services principaux
- [ ] Cas limites testés
- [ ] Commande unique : `pytest`

---

### 3. Database & Storage — Agent : `tech-lead`, `data-secu-docs`

#### 3.1 Schéma
- [ ] Schéma documenté
- [ ] Nommage cohérent
- [ ] Clés primaires définies
- [ ] Types adaptés au contenu
- [ ] Migrations versionnées

#### 3.2 Performance
- [ ] Index sur colonnes filtrées
- [ ] Pas de `SELECT *`
- [ ] Pas de requêtes N+1
- [ ] Transactions atomiques

#### 3.3 Stockage Fichiers
- [ ] Dossier dédié structuré
- [ ] Nommage sans spéciaux
- [ ] Taille max vérifiée

#### 3.4 Sauvegarde
- [ ] Backup scripté
- [ ] Emplacement connu et noté
- [ ] Restauration testée

---

### 4. Hosting & Lancement Local — Agent : `devops-local`

#### 4.1 Lancement
- [ ] Commande unique documentée
- [ ] README avec prérequis
- [ ] Dépendances auto-install
- [ ] Pas d'erreur au premier démarrage

#### 4.2 Containerisation (si utilisée)
- [ ] Dockerfile fonctionnel
- [ ] docker-compose.yml
- [ ] Volumes persistants
- [ ] Port exposé documenté

#### 4.3 Variables d'Environnement
- [ ] `.env.example` présent
- [ ] `.env` dans `.gitignore`
- [ ] Valeurs par défaut raisonnables
- [ ] Démarre sans modification

---

### 5. Configuration & Environnement — Agent : `devops-local`, `data-secu-docs`

#### 5.1 Fichiers de Config
- [ ] Configuration centralisée
- [ ] Valeurs lues depuis env (pas codées en dur)
- [ ] Commentaires en français
- [ ] Pas de duplication

#### 5.2 Dépendances
- [ ] Fichier à jour
- [ ] Versions fixées
- [ ] Dev/prod séparés
- [ ] Pas de dépendance inutilisée
- [ ] Mises à jour régulières

#### 5.3 Documentation
- [ ] README complet
- [ ] Architecture documentée
- [ ] Décisions techniques (ADR)
- [ ] CHANGELOG maintenu

---

### 6. CI/CD & Version Control — Agent : `tech-lead`, `devops-local`

#### 6.1 Commits
- [ ] Commits atomiques
- [ ] Messages explicites en français
- [ ] Pas de fichiers générés
- [ ] `.gitignore` complet

#### 6.2 Branches (si utilisées)
- [ ] `main` stable
- [ ] Nommage cohérent
- [ ] Merges propres

#### 6.3 Automatisation
- [ ] Pre-commit hook lint
- [ ] Tests avant merge
- [ ] Makefile / script de dev

---

### 7. Rate Limiting — Agent : `devops-local`

- [ ] Appels externes limités
- [ ] Pagination sur grosses requêtes
- [ ] Timeout sur chaque appel HTTP
- [ ] Retry limité sur échec

---

### 8. Caching — Agent : `tech-lead`

#### 8.1 Applicatif
- [ ] Données coûteuses en cache
- [ ] TTL défini
- [ ] Invalidation sur mise à jour
- [ ] Taille limitée

#### 8.2 Fichiers & Ressources
- [ ] Headers de cache sur assets
- [ ] Thumbnails/transformés en cache disque
- [ ] Cache disque borné

#### 8.3 Base de Données
- [ ] Requêtes fréquentes en cache
- [ ] Cache invalidé sur écriture
- [ ] Pas de cache temps-réel

---

### 9. Performance & Scalabilité — Agent : `tech-lead`, `designer-qa`

#### 9.1 Réactivité
- [ ] Temps réponse < 200ms
- [ ] Opérations longues en arrière-plan
- [ ] Pas de requête synchrone bloquante
- [ ] Profiling si > 1s

#### 9.2 Ressources
- [ ] Mémoire < 500MB au repos
- [ ] Pas de fuite mémoire
- [ ] CPU < 5% inactif
- [ ] Taille DB surveillée

#### 9.3 Code Asynchrone
- [ ] I/O asynchrones
- [ ] Pas de `sleep()` en production
- [ ] Promesses gérées

---

### 10. Error Tracking & Logs — Agent : `devops-local`, `data-secu-docs`

#### 10.1 Logs
- [ ] Logs structurés (DEBUG, INFO, WARN, ERROR)
- [ ] Événements importants loggés
- [ ] Format clair avec horodatage
- [ ] `LOG_LEVEL` configurable
- [ ] Commentaires en français

#### 10.2 Gestion des Erreurs
- [ ] Erreurs catchées et loggées
- [ ] Messages actionnables
- [ ] Stack trace en mode dev
- [ ] Erreurs critiques en console

#### 10.3 Débogage
- [ ] Mode debug activable
- [ ] Logs verbose disponibles
- [ ] État inspectable (`/status`)

---

### 11. Stabilité & Reprise — Agent : `devops-local`

#### 11.1 Démarrage & Arrêt
- [ ] Démarre avec base vide
- [ ] Arrêt propre (graceful shutdown)
- [ ] Redémarrage idempotent
- [ ] Signal de démarrage loggé

#### 11.2 Tolérance aux Pannes
- [ ] Pas de crash sur entrée invalide
- [ ] Fichier absent/corrompu géré
- [ ] Retry sur perte connexion
- [ ] Opérations atomiques

#### 11.3 Sauvegarde & Restauration
- [ ] Backup documenté et testé
- [ ] Données séparées du code
- [ ] Restauration documentée
- [ ] Données test séparées

---

## Récapitulatif Agent par Agent

| Agent | Sections | Items | Responsabilité |
|-------|----------|-------|----------------|
| `tech-lead` | 2, 3, 6, 8, 9 | ~55 | Architecture, code, dette technique |
| `devops-local` | 4, 5, 6, 7, 10, 11 | ~50 | Lanceurs, monitoring, backup, logs |
| `designer-qa` | 2.5, 9 | ~10 | Tests, edge cases, vérification |
| `data-secu-docs` | 3, 5, 10 | ~20 | Documentation, ADR, CHANGELOG |

## Utilisation

```powershell
# Lancer l'audit complet
.\skills\audit-qualite.ps1

# L'agent Tech Lead peut executer l'audit via le Task tool
# subagent_type: "tech-lead"
# prompt: "Execute le skill audit-qualite sur le projet"
```
