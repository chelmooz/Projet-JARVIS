# JARVIS Portable Edition — Livraison corrigée

## Objet de cette révision

Cette archive corrige des défauts concrets de **sécurité de livraison** et ajoute les premiers contrôles automatisés permettant de prévenir leur réapparition. Elle reste une distribution source destinée à un usage local et portable ; elle ne transforme pas JARVIS en service multi-utilisateur exposé sur Internet.

## Corrections appliquées

| Domaine | Correction | Effet attendu |
|---|---|---|
| Intégrité des téléchargements | L’installation d’Ollama est maintenant refusée si la somme SHA-256 officielle est indisponible ou différente. | Aucun binaire téléchargé sans empreinte vérifiable n’est accepté. |
| Extraction d’archives | Les archives ZIP sont contrôlées avant extraction : chemins sortant de la destination et liens symboliques sont refusés. | Protection contre l’écriture de fichiers hors du répertoire temporaire. |
| Portabilité | Les installateurs système automatiques ne sont plus sélectionnés sur Linux ; l’exécution de `curl | sh` est désactivée sur macOS. | La promesse de ne pas modifier le poste hôte est mieux respectée. |
| Tests | Une suite de régression pytest couvre le refus d’une empreinte absente, la validation d’une empreinte correcte et les archives ZIP malveillantes. | Les corrections essentielles peuvent être vérifiées de façon répétable. |
| Pré-livraison | `scripts/verify_release.py` contrôle la présence des ressources essentielles et l’absence de secrets/configurations locales avant archivage. | Les distributions incomplètes ou contaminées par un `.env` sont détectées. |
| Documentation | Le README ne présente plus l’absence de SHA-256 comme un comportement acceptable. | Les utilisateurs reçoivent une instruction de sécurité cohérente avec le code. |

## Vérifications à lancer

Depuis la racine du projet, utiliser les commandes suivantes :

```bash
python -m pytest -q
python scripts/verify_release.py
python -m py_compile jarvis.py services/*.py controllers/*.py agents/*.py config/*.py graph/*.py models/*.py ports/*.py
```

> La vérification de livraison doit être lancée après les tests et le nettoyage des caches Python ou pytest ; ces caches ne doivent pas figurer dans l’archive finale.

## Limites et prochaines améliorations recommandées

La révision ne met pas en œuvre d’authentification, de gestion fine des rôles, de chiffrement TLS ou de signature cryptographique d’une archive complète. Ces fonctions sont utiles uniquement si l’application quitte son périmètre local `127.0.0.1` ou devient multi-utilisateur. Une future version devrait aussi compléter la suite de tests de toutes les routes FastAPI, du RAG, de la persistance et des parcours d’installation sur Windows, Linux et macOS.
