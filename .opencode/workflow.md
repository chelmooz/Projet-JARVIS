# Guide de Workflow Agent IA — JARVIS Portable

---

## Orchestration du Workflow

### 1. Mode Planification par Défaut

- Activer le mode planification pour **toute tâche non triviale** (3 étapes ou plus, ou décisions architecturales)
- Si quelque chose déraille, **STOPPER** et replanifier immédiatement
- Utiliser le mode planification pour les étapes de vérification, pas seulement pour la construction
- Rédiger des spécifications détaillées en amont pour réduire l'ambiguïté

### 2. Stratégie de Sous-agents

- Utiliser les sous-agents **généreusement** pour garder la fenêtre de contexte principale propre
- Déléguer la recherche, l'exploration et les analyses parallèles aux sous-agents
- Pour les problèmes complexes, allouer plus de puissance de calcul via les sous-agents
- **Une tâche par sous-agent** pour une exécution ciblée

### 3. Boucle d'Auto-amélioration

- Après **toute correction** de l'utilisateur : mettre à jour `BACKLOG.md` avec le modèle correspondant
- Rédiger des règles qui empêchent de reproduire la même erreur
- Itérer sans relâche sur ces leçons jusqu'à ce que le taux d'erreur diminue
- Relire les leçons en début de session pour chaque projet concerné

### 4. Vérification Avant Livraison

- Ne jamais marquer une tâche comme terminée **sans en avoir prouvé le bon fonctionnement**
- Comparer (`diff`) le comportement entre la version principale et les modifications apportées si pertinent
- Se poser la question : *"Un ingénieur senior validerait-il ce travail ?"*
- Lancer les tests, vérifier les logs, démontrer la correction
- **Commandes de validation JARVIS** :
  - `ruff check .` (lint)
  - `pytest tests/` (tests)
  - `python -m py_compile jarvis.py controllers/router.py services/selector.py` (syntax check)

### 5. Exiger l'Élégance (avec discernement)

- Pour les changements non triviaux : marquer une pause et demander *"Existe-t-il une approche plus élégante ?"*
- Si un correctif semble bricolé : *"En sachant tout ce que je sais maintenant, implémenter la solution élégante"*
- Ne pas appliquer cette règle aux correctifs simples et évidents — **ne pas sur-ingénierer**
- Challenger son propre travail avant de le présenter

### 6. Correction de Bugs Autonome

- Face à un rapport de bug : **le corriger directement**, sans demander à être guidé
- Identifier les logs, les erreurs, les tests en échec — puis les résoudre
- **Zéro changement de contexte** requis de la part de l'utilisateur
- Corriger les tests CI en échec sans avoir à y être invité

---

## Gestion des Tâches

1. **Planifier d'abord** : Rédiger un plan dans `BACKLOG.md` avec des éléments cochables
2. **Valider le plan** : Vérifier avant de commencer l'implémentation
3. **Suivre la progression** : Cocher les éléments au fur et à mesure
4. **Expliquer les changements** : Fournir un résumé de haut niveau à chaque étape
5. **Documenter les résultats** : Ajouter une section de revue dans `BACKLOG.md`
6. **Capitaliser les leçons** : Mettre à jour `BACKLOG.md` après chaque correction

---

## Principes Fondamentaux

- **Simplicité avant tout** : Rendre chaque changement aussi simple que possible. Impact minimal sur le code.
- **Zéro paresse** : Identifier les causes racines. Aucun correctif temporaire. Standards d'un développeur senior.
- **Impact minimal** : Ne toucher que ce qui est nécessaire. Aucun effet de bord, aucun nouveau bug introduit.

---

## Skills Activés (projet JARVIS)

| Skill | Fichier | Usage |
|-------|---------|-------|
| `clean-code` | `~/.config/opencode/skills/clean-code/SKILL.md` | Lisibilité, fonctions courtes, noms explicites, DRY, SRP |
| `kiss` | `~/.config/opencode/skills/kiss/SKILL.md` | Solution la plus simple qui marche, pas de sur-ingénierie |
| `solid` | `~/.config/opencode/skills/solid/SKILL.md` | Architecture modulaire, inversion de dépendances, interfaces |

> Ces skills sont chargés depuis la config utilisateur (`~/.config/opencode/`) et s'appliquent au projet JARVIS.