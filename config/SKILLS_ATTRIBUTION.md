# Attribution — Obra Superpowers (MIT License)

Certains prompts de `config/skills.json` (skills `kill_coding`, `code_review`,
`systematic_debugging`) sont adaptés de skills issus du repo open source
[`obra/superpowers`](https://github.com/obra/superpowers), sous licence MIT.

## Fichiers sources utilisés

| Skill JARVIS | Fichiers sources (branche `main` de obra/superpowers) |
|---|---|
| `kill_coding` | `skills/test-driven-development/SKILL.md`, `skills/test-driven-development/writing-good-tests.md` |
| `code_review` | `skills/requesting-code-review/code-reviewer.md` (section "What to Check" uniquement) |
| `systematic_debugging` | `skills/systematic-debugging/SKILL.md` |

Le contenu a été traduit/condensé en français et adapté au format de
`config/skills.json` (prompts injectés dans le contexte LLM de l'agent `@dev`).

## Licence MIT — Copyright (c) 2025 Jesse Vincent

```
MIT License

Copyright (c) 2025 Jesse Vincent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Définitions hors périmètre (pas d'import)

Les fichiers suivants du repo source ont été délibérément exclus :

- `skills/requesting-code-review/SKILL.md` — repose sur le dispatch d'un
  subagent reviewer avec SHA git, inapplicable à `@dev` (réponse en un tour
  dans un chat, pas de session autonome multi-agents).
- `skills/receiving-code-review/` — protocole comportemental pour un agent qui
  *reçoit* une critique humaine, sans rapport avec un skill de revue de code.
- Skills orientés orchestration multi-agents (`brainstorming`, `writing-plans`,
  `executing-plans`, `dispatching-parallel-agents`, `using-git-worktrees`,
  `finishing-a-development-branch`, `subagent-driven-development`) — supposent
  un agent avec accès git/shell autonome sur plusieurs tours. Sujet à
  réévaluer si `@dev` gagne des capacités d'exécution multi-étapes.