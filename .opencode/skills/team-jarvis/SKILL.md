---
name: team-jarvis
description: >
  Use when you need to delegate to one of the 5 JARVIS team agents:
  orchestrateur (coordination), tech-lead (code/architecture),
  devops-local (infra/scripts), designer-qa (UX/tests),
  or data-secu-docs (data/security/docs).
---

# Team JARVIS — 5 Subagents

Invoke via Task tool with `subagent_type: "<agent-name>"`.

## Quand utiliser quel agent

| Agent | subagent_type | Quand l'utiliser |
|-------|---------------|------------------|
| **Orchestrateur** | `orchestrateur` | Nouveau besoin, planification, priorisation, arbitrage entre agents |
| **Tech Lead** | `tech-lead` | Architecture, code review, refactoring, choix techniques, clean code |
| **DevOps Local** | `devops-local` | Scripts de lancement, automatisation, backups, monitoring, runbooks |
| **Designer QA** | `designer-qa` | UX/UI, plans de test, bugs, edge cases, validation qualité |
| **Data/Sécu/Docs** | `data-secu-docs` | Pipelines data, sécurité, documentation technique, ADR |

## Règles globales "Muscle ton jeu"

- Une seule indentation par méthode → sinon, découper.
- Éviter `else` → préférer les early returns.
- Encapsuler les types primitifs → Value Objects métier.
- Encapsuler les collections → objets dédiés.
- Make it work → Make it right → Make it fast.
- Nommer clairement (intention > brièveté).
- Typer systématiquement (quand le langage le permet).
- Keep It Short (KISS) : 1 fonction = 1 responsabilité.

## Flux de travail

1. L'Orchestrateur reçoit le besoin → clarifie en 1 question max.
2. Consulte le Tech Lead pour l'effort technique.
3. Délègue aux agents concernés.
4. Le Designer QA valide le résultat.
5. Data/Sécu/Docs documente.
