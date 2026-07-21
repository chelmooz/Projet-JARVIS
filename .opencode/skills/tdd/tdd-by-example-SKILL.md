---
name: tdd-by-example
description: "Discipline TDD (Test-Driven Development) : micro-cycle RED/GREEN/REFACTOR, patterns de test (Test List, Fake It, Triangulate, Obvious Implementation, Learning Test, Regression Test), patterns de conception émergents (Value Object, Null Object, Command, Template Method, Sprout Method), patterns xUnit (Fixture, Setup/Teardown, Test Runner). Complète clean-code-discipline (3.I, F.I.R.S.T) par le déroulé pas-à-pas du cycle. À consulter systématiquement avant d'écrire le moindre test ou code de production."
---

# Discipline TDD — cycle RED/GREEN/REFACTOR et patterns associés

**Portée** : Traduction de la pratique du Test-Driven Development en directives impératives pour agents IA. Complète clean-code-discipline par le déroulé opérationnel du cycle de développement piloté par les tests.

## 1. RTOC (Rôle / Tâche / Objectif / Contraintes)

### RÔLE
Tu pratiques le TDD à la lettre : jamais de code de production sans un test qui échoue avant lui, jamais plus de code que nécessaire pour le faire réussir.

### TÂCHE
Faire avancer une fonctionnalité par une suite de micro-cycles RED → GREEN → REFACTOR, chacun assez petit pour durer quelques minutes, en s'appuyant sur une Test List tenue à jour.

### OBJECTIF
Un code entièrement couvert par construction, une suite de tests qui documente le comportement, une conception qui émerge du refactoring plutôt que d'être devinée à l'avance.

### CONTRAINTES (Non négociables)
- **Trois lois du TDD** : Aucun code de production sans test qui échoue au préalable ; pas plus de test que nécessaire pour échouer ; pas plus de code que nécessaire pour réussir.
- **Cycle court** : RED → GREEN → REFACTOR ne dépasse pas quelques minutes. Au-delà, le test était trop gros — le découper.
- **Test List vivante** : Écrite avant le premier test, mise à jour à chaque cycle (ajout de cas découverts, suppression de cas traités).
- **Étanchéité des phases** : Aucun refactoring pendant RED. Aucune généralisation anticipée pendant GREEN.
- **Assert First** : L'assertion attendue s'écrit avant le setup qui la rend possible, jamais après.

## 2. CoT — Cycles de raisonnement IA

### CoT-A — Micro-cycle d'écriture
1. **Test List** : Choisir le cas le plus simple qui fait progresser la compréhension du problème, pas le plus simple à écrire (3.A).
2. **RED** : Écrire l'assertion attendue avant le setup. Une erreur d'import ou de nom compte comme un échec valide.
3. **GREEN** : Fake It si la solution n'est pas encore claire (3.B), Triangulate si deux exemples sont nécessaires pour généraliser (3.C), Obvious Implementation si évident et sûr (3.D).
4. **Vérification** : Relancer toute la suite, pas seulement le nouveau test.
5. **REFACTOR** : Appliquer clean-code-discipline (nommage, taille, duplication) sur le test et le code de production, sans changer le comportement.
6. **Mise à jour** : Rayer le cas traité de la Test List, ajouter tout cas découvert pendant l'implémentation.

### CoT-B — Cycle de revue TDD
1. **Chronologie** : Le test précède-t-il le code, ou a-t-il été écrit après coup pour habiller une implémentation existante ?
2. **Isolation** : Le test dépend-il de l'état ou de l'ordre d'exécution d'un autre test ? (3.A)
3. **Granularité** : Le cycle a-t-il dépassé quelques minutes ? Signe d'un test trop ambitieux à redécouper.
4. **Frontières** : Une dépendance tierce nouvellement intégrée est-elle couverte par un Learning Test ? (3.F)
5. **Conception** : Un pattern de la section 3.H-3.J a-t-il émergé du refactoring, ou a-t-il été plaqué par anticipation (YAGNI) ?
6. **Verdict** : Citer les violations précises (ex. "test écrit après le code, fichier X ligne Y").

## 3. Catalogue de patterns

### 3.A — Isolated Test / Test List
- **Isolated Test** : Chaque test construit son propre fixture. Aucun état partagé mutable entre tests.
- **Test List** : Liste des cas à couvrir (nominal, limites, erreurs), tenue à jour en continu, distincte du code des tests eux-mêmes.

### 3.B — Fake It
- Faire passer le test au vert par le moyen le plus court, y compris une constante en dur, pour obtenir un signal vert rapide puis avancer par petits pas.
- Usage : la forme finale du code n'est pas encore claire, ou la page blanche bloque l'écriture.

### 3.C — Triangulate
- Ne généraliser une implémentation qu'à partir de deux exemples concrets et différents qui l'exigent tous les deux.
- Si un test peut être satisfait par une implémentation factice, ajouter un second test qui l'élimine avant de généraliser.

### 3.D — Obvious Implementation
- Écrire directement la solution quand elle est évidente et à faible risque, sans passer par Fake It.
- Garde-fou : si elle casse un test déjà vert, revenir à Fake It/Triangulate pour la suite.

### 3.E — Starter Test
- Démarrer une nouvelle fonctionnalité par le cas le plus simple possible (entrée vide, cas dégénéré) pour obtenir une première structure de code sur laquelle itérer.

### 3.F — Learning Test / Regression Test
- **Learning Test** : Fige le comportement observé d'une dépendance tierce (lib, API) avant intégration ; casse dès que la dépendance change de comportement.
- **Regression Test** : Écrit pour reproduire un bug signalé (RED) avant toute correction ; reste dans la suite en permanence.

### 3.G — Break
- Chercher volontairement à faire échouer une implémentation crue correcte (cas limites, entrées invalides) avant de la considérer terminée.

### 3.H — Value Object / Null Object
- **Value Object** : Objet immuable défini par ses attributs, égalité par valeur. Signal d'émergence : comparaison par identité (`is`) sur un objet censé être une valeur.
- **Null Object** : Objet représentant l'absence de valeur avec la même interface que le cas normal. Signal d'émergence : `if x is None` répété à plusieurs niveaux d'appel.

### 3.I — Command / Template Method / Sprout Method
- **Command** : Action encapsulée dans un objet exécutable, différable ou journalisable.
- **Template Method** : Squelette d'algorithme fixé dans une base, étapes déléguées aux sous-classes. Signal : plusieurs implémentations qui ne diffèrent que par une étape.
- **Sprout Method/Class** : Nouvelle logique écrite à côté d'un code existant non testé, testée isolément, avant raccordement — pertinent sur un fichier sans couverture suffisante pour être modifié en sécurité.

### 3.J — Composite / Collecting Parameter
- **Composite** : Un élément individuel et une collection d'éléments traités via la même interface.
- **Collecting Parameter** : Objet mutable passé en paramètre à plusieurs méthodes qui l'enrichissent tour à tour. À utiliser avec parcimonie (état partagé mutable).

### 3.K — Fixture / Setup-Teardown
- **Fixture / External Fixture** : État préparé avant un test ; toute ressource externe est libérée dans un bloc garanti (`finally`, fixture `yield`), même en cas d'échec.
- **Setup/Teardown** : Préférer les fixtures `yield` aux paires setup/teardown explicites, pour garantir l'exécution même en cas d'exception.

### 3.L — Exception Test / Test Runner
- **Exception Test** : Vérifie qu'une opération lève l'exception attendue (`pytest.raises`), pas seulement l'absence d'erreur inattendue.
- **Test Runner** : Isoler en suite séparée un fichier à fort taux d'échec, pour suivre sa résorption cycle par cycle sans noyer le signal dans le run global.

## 4. Discipline d'exécution IA (Code of Conduct)
- **Vert rapide** : Un cycle RED→GREEN qui dépasse quelques minutes signale un test trop ambitieux — le redécouper immédiatement.
- **Zéro anticipation** : Jamais de code de production en avance sur le test qui le justifie, même si la suite semble évidente. Loi 1, non négociable sous pression.
- **Refactoring non optionnel** : Fait partie intégrante du cycle, jamais une étape reportée faute de temps.
- **Test List croissante** : Signal qu'il faut redécouper la fonctionnalité en tranches plus petites avant de continuer.
- **Test cassé après refactoring** : Corriger le test lui-même s'il testait la structure plutôt que le comportement, pas seulement le code de production.
- **Boy Scout Rule** : Chaque fichier touché ressort plus propre, et mieux couvert, qu'il n'est entré.
