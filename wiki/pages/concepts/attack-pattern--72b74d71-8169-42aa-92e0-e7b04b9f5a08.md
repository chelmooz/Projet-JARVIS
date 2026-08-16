---
id: attack-pattern--72b74d71-8169-42aa-92e0-e7b04b9f5a08
title: "Account Discovery"
type: concept
agent: "@cyber"
tags: []
sources: ["mitre-attack-v19.1:attack-pattern--72b74d71-8169-42aa-92e0-e7b04b9f5a08"]
links_to: []
created: 2026-08-17
updated: 2026-08-17
---

# Account Discovery

## Résumé
Account Discovery: Adversaries may attempt to get a listing of valid accounts, usernames, or email addresses on a system or within a compromised envir...

## Contenu
Account Discovery: Adversaries may attempt to get a listing of valid accounts, usernames, or email addresses on a system or within a compromised environment. This information can help adversaries determine which accounts exist, which can aid in follow-on behavior such as brute-forcing, spear-phishing attacks, or account takeovers (e.g., [Valid Accounts](https://attack.mitre.org/techniques/T1078)).

Adversaries may use several methods to enumerate accounts, including abuse of existing tools, built-in commands, and potential misconfigurations that leak account names and roles or permissions in the targeted environment.

For examples, cloud environments typically provide easily accessible interfaces to obtain user lists.(Citation: AWS List Users)(Citation: Google Cloud - IAM Servie Accounts List API) On hosts, adversaries can use default [PowerShell](https://attack.mitre.org/techniques/T1059/001) and other command line functionality to identify accounts. Information about email addresses and accounts may also be extracted by searching an infected system’s files.

## Liens
(Aucun lien pour l'instant — sera enrichi en Phase 2)

## Sources
- `mitre-attack-v19.1#attack-pattern--72b74d71-8169-42aa-92e0-e7b04b9f5a08`
