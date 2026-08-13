# ADR-001 : Architecture MVC + Ports (KISS avec contrats)

**Statut :** Accepté  
**Date :** 2026-05-28  
**Décideur :** Tech Lead + équipe JARVIS  

## Contexte

Le projet JARVIS Portable a subi un refactoring depuis une Clean Architecture complexe (Domain / UseCases / Ports / Adapters / Infra) vers une architecture MVC simplifiée. La roadmap SOLID.md préconise la Clean Architecture avec TDD strict.

## Décision

On adopte **MVC + Ports** :

- **MVC** pour la structure générale : `models/`, `controllers/`, `services/`
- **Ports (interfaces abstraites)** dans `ports/` pour les contrats entre couches
- Les services concrets dans `services/` implémentent ces ports
- **Pas de couche Use Cases séparée** — la logique métier reste dans les services et le graph
- **Pas de Clean Architecture stricte** — la valeur perçue ne justifie pas la complexité

## Justification

1. **KISS prime** : le projet tient dans 30 fichiers, 5 services, 357 lignes de routes — la Clean Architecture multiplierait les couches sans bénéfice tangible
2. **Testabilité suffisante** : les ports permettent le mocking, les services sont des classes simples
3. **Évolution pragmatique** : si un service devient complexe, on l'extrait en use case — pas avant
4. **Portabilité** : le lanceur `jarvis.py` est le point d'entrée unique, pas besoin d'une couche infra dédiée

## Conséquences

- Les ports doivent précéder les implémentations pour les nouvelles fonctionnalités
- Les tests doivent cibler les services via leurs ports (mocking possible)
- Pas d'injection de dépendance framework — les dépendances sont passées manuellement (simple, visible)
