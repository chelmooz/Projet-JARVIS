# Contribuer à JARVIS Portable

## Principes

- **1 fonction = 1 responsabilité** (pas plus de 15 lignes)
- **Early return** — pas de `else` inutile
- **Nommage explicite** — l'intention > la brieveté
- **Typage systématique** (quand le langage le permet)
- **Keep It Short (KISS)** : chaque fichier fait une seule chose

## Workflow TDD

1. **RED** : écris un test qui échoue pour le comportement attendu
2. **GREEN** : implémente le minimum pour faire passer le test
3. **REFACTOR** : nettoie sans casser les tests

Toute modification doit être accompagnée d'un test correspondant.

## Commandes

```bash
# Lancer les tests
python -m pytest tests/ -v

# Lancer le serveur
python jarvis.py

# Lancer l'API seule
python -m uvicorn controllers.router:app --reload
```

## Structure

```
controllers/    → routes API (couche HTTP)
services/       → logique metier (implem)
ports/          → interfaces abstraites (contrats)
models/         → dataclasses pures
agents/         → agents IA (factory + 5 agents)
graph/          → pipeline d'orchestration
```

## Règles

- Ne jamais commit sans passer les tests
- Ne jamais modifier un port sans mettre à jour tous les services qui l'implémentent
- Toujours utiliser les ports (pas les services concrets) dans les signatures de fonctions inter-couches
