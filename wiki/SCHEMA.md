# 📐 SCHEMA.md — Conventions de formatage des pages Wiki

Ce document définit le format standard de toutes les pages générées dans `wiki/pages/`. 
Il suit la méthodologie LLM Wiki (Karpathy) adaptée pour JARVIS.

## 1. Frontmatter YAML

Chaque page DOIT commencer par un bloc YAML délimité par `---`. Ce frontmatter est critique pour l'indexation VectorService (O2 - LazyGraphRAG).

```yaml
---
id: concept-xxx-nom-unique
title: Titre Humain de la Page
type: concept | procedure | skill
agent: "@cyber" | "@dev" | "@network" | "@hardware" | "@vision"
tags: [tag1, tag2]
sources: ["mitre-attack.jsonl:T1234", "codesearchnet-python.jsonl:repo-abc"]
links_to: ["concept-yyy-autre-page"]
created: 2026-08-17
updated: 2026-08-17
---
```

## 2. Titre
H1 en Markdown, reprenant le champ `title` du frontmatter.

## 3. Résumé
Un paragraphe de synthèse (max 150 mots) expliquant le concept ou la procédure.

## 4. Contenu
Corps principal de la page :
- Pour un **concept** : définition, caractéristiques, exemples.
- Pour une **procédure** : étapes numérotées, pré-requis, résultats attendus.
- Pour un **skill** : cas d'usage, prompt type, limites connues.

## 5. Liens
Section explicite listant les relations sémantiques (référence le champ `links_to` du frontmatter).
- [[concept-yyy-autre-page]] - Description de la relation.

## 6. Sources
Liste exhaustive des entrées JSONL utilisées pour générer cette page, avec leur `id`.
- Source 1 : `mitre-attack.jsonl#T1234`
- Source 2 : `...`