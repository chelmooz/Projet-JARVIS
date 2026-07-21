# Protocoles & Principes de Codage

## SOLID
- **SRP** : une classe = une responsabilité
- **OCP** : ouvert à l'extension, fermé à la modification
- **LSP** : sous-classe remplace parente sans casser le contrat
- **ISP** : interfaces spécifiques plutôt qu'une seule "fat interface"
- **DIP** : dépendre d'abstractions, pas d'implémentations concrètes

## KISS — Keep It Simple, Stupid
- La simplicité est l'objectif principal. Solution la plus directe possible.
- Complexité accidentelle à éliminer.
- Toutes les décisions d'architecture passent par KISS en premier.

## Clean Code
- Nommage qui révèle l'intention
- Fonctions < 20 lignes, une seule chose
- Commentaires utiles uniquement (règle : le code s'explique seul)
- Pas de code mort commenté
- Exceptions plutôt que codes retour

## MVC — Model-View-Controller
- Modèle = données + logique métier
- Vue = présentation uniquement
- Contrôleur = orchestration (mince)

## TDD — Red-Green-Refactor
1. RED : écrire un test qui échoue
2. GREEN : code minimal pour passer
3. REFACTOR : améliorer sans casser

## DRY — Don't Repeat Yourself
- Chaque connaissance une seule représentation
- Rule of Three avant factorisation

## YAGNI — You Aren't Gonna Need It
- N'implémente que ce qui est nécessaire maintenant
- Pas d'anticipation inutile

## LoD — Law of Demeter
- Ne parle qu'à tes voisins directs
- Pas de chaînes d'appels (`a.b.c.d()`)

## CQRS
- Séparer les opérations de lecture (Query) et d'écriture (Command)

## Event Sourcing
- Stocker les changements comme une séquence d'événements

## GoF Patterns
- Créationnels : Singleton, Factory, Builder, Prototype
- Structurels : Adapter, Decorator, Facade, Composite, Proxy
- Comportementaux : Observer, Strategy, Command, Iterator, Template

## Repository Pattern
- Abstraction de la couche d'accès aux données
- Interface = collection en mémoire

## Hexagonal Architecture (Ports & Adapters)
- Domaine métier au centre
- Ports = interfaces
- Adapters = implémentations (HTTP, SQL, etc.)

## BDD
- Comportement attendu en langage naturel (Given/When/Then)
- Alignement métier-technique

## Boy Scout Rule
- Laisse le code plus propre qu'à ton arrivée

## Fail Fast
- Détecter et signaler les erreurs le plus tôt possible
- Valider les entrées en début de fonction

## Composition over Inheritance
- Préférer la composition à l'héritage
- Évite le fragile base class problem

## Tell, Don't Ask
- Demander à un objet d'agir plutôt que d'inspecter son état

## Separation of Concerns (SoC)
- Chaque module gère une seule préoccupation
- Architecture en couches (Présentation / Domaine / Infrastructure)

## Lazy Loading
- Charger les ressources uniquement quand nécessaires

## Defensive Programming
- Anticiper et gérer les cas d'erreur systématiquement
- Timeouts, validation, valeurs par défaut

## Convention over Configuration
- Conventions réduisent les décisions explicites
- Moins de configuration = plus de productivité
