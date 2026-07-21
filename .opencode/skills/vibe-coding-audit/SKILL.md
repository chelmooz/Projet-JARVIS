---
name: vibe-coding-audit
description: Audite un projet développé en "vibe coding" (code généré/itéré principalement via un assistant IA, souvent sans specs formelles ni review humaine systématique) en cherchant les décisions cachées, non documentées ou non testées qui font tenir le projet debout par accident plutôt que par conception. Utiliser ce skill dès que l'utilisateur demande un audit, une revue de robustesse, une revue avant mise en prod, ou une "code review" d'un projet vibe-codé, même s'il ne prononce pas le mot "audit" — par exemple "est-ce que mon code tient la route", "peux-tu vérifier ce projet avant que je le déploie", "j'ai codé ça avec Claude/Cursor/Copilot, peux-tu regarder si c'est solide". Ce skill s'applique aussi bien à un repo entier qu'à un module ou une fonctionnalité précise.
---

# Audit d'un projet vibe-codé

## Principe

Un projet vibe-codé, c'est un peu comme deux chercheurs qui partent des mêmes données brutes (le même prompt, le même besoin) et arrivent à des résultats radicalement différents selon les choix qu'ils ont faits en chemin. Le code qui tourne aujourd'hui n'est pas nécessairement le code qui reflète le besoin réel : c'est souvent le premier code qui a fait passer le test, taire l'erreur, ou satisfaire la démo. Ça ne veut pas dire que c'est faux — mais que ça n'a pas été vérifié.

L'objectif de cet audit n'est pas de re-coder le projet, mais de révéler les décisions invisibles qui ont été prises "en passant" pendant les itérations avec l'IA, et de vérifier si le résultat survit quand on change les conditions — exactement comme une analyse de robustesse en recherche.

Ne jamais se contenter de lire le code une seule fois et conclure "ça a l'air bien". Le but est de **stress-tester** le raisonnement qui a produit ce code, pas seulement sa syntaxe.

## Les 5 degrés de liberté à traquer

Pour chaque fonctionnalité auditée, chercher des traces de ces 5 catégories de décisions cachées (l'équivalent des "choix méthodologiques" du chercheur) :

| # | Chez le chercheur | Chez le vibe-codeur | Ce qu'il faut chercher dans le code |
|---|---|---|---|
| 1 | Quelles variables inclure | Quelles dépendances/librairies choisies | Choix de libs, versions, paramètres par défaut jamais questionnés |
| 2 | Garder ou virer les valeurs extrêmes | Gestion des cas limites | Inputs vides, null, très grands volumes, caractères spéciaux, concurrence |
| 3 | Forme mathématique du modèle | Architecture retenue | Sync vs async, structure de données, découpage des responsabilités |
| 4 | Hypothèses statistiques implicites | Hypothèses d'environnement implicites | "Ça suppose qu'il n'y a qu'un seul utilisateur", "ça suppose que l'API répond toujours en <1s" |
| 5 | p-hacking (tester jusqu'au résultat magique) | Coder jusqu'à ce que le test/la démo passe | Voir section dédiée ci-dessous |

## Procédure d'audit

### Étape 1 — Cartographier les décisions non documentées

Parcourir le code (ou la partie concernée) et lister, pour chaque choix structurant, s'il est :
- **Justifié** (commentaire, doc, message de commit qui explique le pourquoi)
- **Implicite** (ça marche, mais personne n'a écrit pourquoi ce choix plutôt qu'un autre)

Ne pas se limiter à lire le code final : si l'historique git est disponible, regarder les commits/diffs successifs. Un projet vibe-codé montre souvent un pattern révélateur — plusieurs tentatives, un revert, un "fix" qui rajoute un cas particulier sans toucher au reste. Ce pattern est le signal le plus fiable de decision cachée.

### Étape 2 — Détecter le "p-hacking" du code

C'est l'étape la plus importante et la plus spécifique à ce skill. Chercher activement les signes que le code a été itéré jusqu'à obtenir le résultat voulu, sans compréhension du pourquoi. Signaux typiques :

- **Valeurs magiques alignées sur les fixtures de test** (un seuil, un index, un timeout qui correspond exactement aux données du test et à rien d'autre)
- **Try/except (ou équivalent) trop larges** qui avalent l'erreur au lieu de la traiter — le code "marche" simplement parce que l'exception ne remonte plus
- **Tests désactivés, skippés, ou dont l'assertion a été affaiblie** au lieu d'être corrigée
- **Mocks qui masquent le vrai problème** (on mocke la fonction qui plantait plutôt que de la corriger)
- **Retry loops ajoutés sans investiguer la cause de l'échec initial**
- **Code dupliqué avec une variante "qui marche"** à côté d'une version commentée "qui ne marchait pas" — sans qu'on sache pourquoi
- **Cast de type ou conversion forcée** ajoutée pour faire taire une erreur plutôt que pour corriger la donnée en amont

Chacun de ces signaux doit être noté comme "résultat potentiellement illusoire" : ça passe la démo, mais on n'a aucune garantie que ça survivra à un cas légèrement différent.

### Étape 3 — Contrôler comme un chercheur contrôlerait ses variables

Pour chaque fonctionnalité clé, appliquer le même raisonnement que l'exemple télétravail/productivité de la vidéo : partir du résultat brut ("ça marche dans la démo") et ajouter des "variables de contrôle" une par une pour voir si le résultat tient :

1. **Contrôle input** : que se passe-t-il avec un input vide, malformé, ou à l'échelle x100 ?
2. **Contrôle environnement** : est-ce que ça marche encore avec une autre config, un autre OS, sans la variable d'env que le dev avait localement ?
3. **Contrôle temporel** : que se passe-t-il si un appel réseau est lent, timeout, ou renvoie une erreur ?
4. **Contrôle concurrence** : que se passe-t-il si deux utilisateurs/process font l'action en même temps ?
5. **Contrôle adversarial** : que se passe-t-il si l'input est délibérément hostile (injection, dépassement de buffer, valeurs négatives là où on attend du positif) ?

Si le résultat "s'effondre" dès qu'on ajoute un contrôle (comme les 12% qui tombent à 1%), c'est le signal que la fonctionnalité initiale n'était pas robuste — elle était juste non testée dans ces conditions.

### Étape 4 — Vérifier la reproductibilité

Équivalent de la "crise de réplication" : est-ce que quelqu'un d'autre (ou vous, dans 3 mois) peut reprendre ce projet et obtenir le même comportement ?

- Dépendances versionnées/pinnées ou "ça dépend de ce qui traîne sur la machine" ?
- Setup documenté ou tribal knowledge uniquement dans la tête de qui a vibe-codé ?
- Comportement déterministe ou dépend de l'ordre d'exécution, de l'heure, de données externes non mockées dans les tests ?
- Y a-t-il un état caché (fichier local, variable globale, cache) dont dépend le bon fonctionnement sans que ce soit explicite ?

## Format du rapport d'audit

Produire un rapport structuré (fichier markdown si le projet est conséquent, sinon réponse directe dans la conversation pour un module ciblé) avec ces sections :

1. **Résumé exécutif** — le projet tient-il "par conception" ou "par accident" ? 2-3 phrases, direct.
2. **Décisions non documentées** — tableau : décision / endroit dans le code / risque si l'hypothèse est fausse
3. **Signaux de "p-hacking" du code** — liste des patterns suspects trouvés à l'étape 2, avec fichier + ligne
4. **Résultats des contrôles de robustesse** — pour chaque fonctionnalité clé testée à l'étape 3, indiquer si elle survit ou s'effondre, et sous quelle condition
5. **Risques de non-reproductibilité** — ce qui empêche un tiers de reprendre le projet à l'identique
6. **Recommandations priorisées** — classées par : bloquant avant prod / important mais pas bloquant / cosmétique

Toujours donner des exemples concrets (fichier, ligne, extrait) plutôt que des généralités du type "le code manque de robustesse". Le but est que l'utilisateur puisse rouvrir son projet et retrouver immédiatement de quoi vous parlez.

## Ton à adopter

Rester factuel et constructif, jamais alarmiste. Un projet vibe-codé qui marche n'est pas un échec — c'est un point de départ légitime. L'audit sert à transformer "ça a l'air de marcher" en "on sait pourquoi ça marche et dans quelles limites", pas à discréditer la méthode de développement elle-même.
