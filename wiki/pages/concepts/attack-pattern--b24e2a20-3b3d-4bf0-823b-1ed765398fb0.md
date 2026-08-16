---
id: attack-pattern--b24e2a20-3b3d-4bf0-823b-1ed765398fb0
title: "Account Access Removal"
type: concept
agent: "@cyber"
tags: []
sources: ["mitre-attack-v19.1:attack-pattern--b24e2a20-3b3d-4bf0-823b-1ed765398fb0"]
links_to: []
created: 2026-08-17
updated: 2026-08-17
---

# Account Access Removal

## Résumé
Account Access Removal: Adversaries may interrupt availability of system and network resources by inhibiting access to accounts utilized by legitimate...

## Contenu
Account Access Removal: Adversaries may interrupt availability of system and network resources by inhibiting access to accounts utilized by legitimate users. Accounts may be deleted, locked, or manipulated (ex: changed credentials, revoked permissions for SaaS platforms such as Sharepoint) to remove access to accounts.(Citation: Obsidian Security SaaS Ransomware June 2023) Adversaries may also subsequently log off and/or perform a [System Shutdown/Reboot](https://attack.mitre.org/techniques/T1529) to set malicious changes into place.(Citation: CarbonBlack LockerGoga 2019)(Citation: Unit42 LockerGoga 2019)

In Windows, [Net](https://attack.mitre.org/software/S0039) utility, <code>Set-LocalUser</code> and <code>Set-ADAccountPassword</code> [PowerShell](https://attack.mitre.org/techniques/T1059/001) cmdlets may be used by adversaries to modify user accounts. Accounts could also be disabled by Group Policy. In Linux, the <code>passwd</code> utility may be used to change passwords. On ESXi servers, accounts can be removed or modified via esxcli (`system account set`, `system account remove`).

Adversaries who use ransomware or similar attacks may first perform this and other Impact behaviors, such as [Data Destruction](https://attack.mitre.org/techniques/T1485) and [Defacement](https://attack.mitre.org/techniques/T1491), in order to impede incident response/recovery before completing the [Data Encrypted for Impact](https://attack.mitre.org/techniques/T1486) objective. 

## Liens
(Aucun lien pour l'instant — sera enrichi en Phase 2)

## Sources
- `mitre-attack-v19.1#attack-pattern--b24e2a20-3b3d-4bf0-823b-1ed765398fb0`
