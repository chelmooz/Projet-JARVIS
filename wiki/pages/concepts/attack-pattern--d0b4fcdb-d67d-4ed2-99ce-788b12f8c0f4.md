---
id: attack-pattern--d0b4fcdb-d67d-4ed2-99ce-788b12f8c0f4
title: "/etc/passwd and /etc/shadow"
type: concept
agent: "@cyber"
tags: []
sources: ["mitre-attack-v19.1:attack-pattern--d0b4fcdb-d67d-4ed2-99ce-788b12f8c0f4"]
links_to: []
created: 2026-08-17
updated: 2026-08-17
---

# /etc/passwd and /etc/shadow

## Résumé
/etc/passwd and /etc/shadow: Adversaries may attempt to dump the contents of <code>/etc/passwd</code> and <code>/etc/shadow</code> to enable offline p...

## Contenu
/etc/passwd and /etc/shadow: Adversaries may attempt to dump the contents of <code>/etc/passwd</code> and <code>/etc/shadow</code> to enable offline password cracking. Most modern Linux operating systems use a combination of <code>/etc/passwd</code> and <code>/etc/shadow</code> to store user account information, including password hashes in <code>/etc/shadow</code>. By default, <code>/etc/shadow</code> is only readable by the root user.(Citation: Linux Password and Shadow File Formats)

Linux stores user information such as user ID, group ID, home directory path, and login shell in <code>/etc/passwd</code>. A "user" on the system may belong to a person or a service. All password hashes are stored in <code>/etc/shadow</code> - including entries for users with no passwords and users with locked or disabled accounts.(Citation: Linux Password and Shadow File Formats)

Adversaries may attempt to read or dump the <code>/etc/passwd</code> and <code>/etc/shadow</code> files on Linux systems via command line utilities such as the <code>cat</code> command.(Citation: Arctic Wolf) Additionally, the Linux utility <code>unshadow</code> can be used to combine the two files in a format suited for password cracking utilities such as John the Ripper - for example, via the command <code>/usr/bin/unshadow /etc/passwd /etc/shadow > /tmp/crack.password.db</code>(Citation: nixCraft - John the Ripper). Since the user information stored in <code>/etc/passwd</code> are linked to the password hashes in <code>/etc/shadow</code>, an adversary would need to have access to both.

## Liens
(Aucun lien pour l'instant — sera enrichi en Phase 2)

## Sources
- `mitre-attack-v19.1#attack-pattern--d0b4fcdb-d67d-4ed2-99ce-788b12f8c0f4`
