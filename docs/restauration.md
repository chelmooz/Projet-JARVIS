# Restauration des données JARVIS

Procédure de sauvegarde et de restauration des données du projet JARVIS
(FastAPI, mono-utilisateur, portable Windows).

## Où sont les données

| Donnée            | Emplacement                          | Contenu |
|-------------------|--------------------------------------|---------|
| `memory/`         | `J:\Projet JARVIS\memory`            | Conversations, habitudes, index vectoriel, analytics, metrics |
| `logs/`           | `J:\Projet JARVIS\logs`              | Journaux de l'API et de restauration (`restore.log`) |
| `config/`         | `J:\Projet JARVIS\config`            | Préférences modèles, profils d'agents, routage, adaptateurs |

Ces trois répertoires constituent le périmètre sauvegardé/restauré.

## 1. Créer un backup

### Windows (recommandé)
```powershell
cd J:\Projet JARVIS
pwsh .\scripts\backup.ps1
```
Produit `backups/jarvis-backup-AAAAmmjj_HHMMSS.zip` (archive `memory/`, `logs/`, `config/`).

### Planifier (optionnel)
```powershell
python scripts/schedule_backup.py --interval daily     # tâche planifiée Windows
python scripts/schedule_backup.py remove               # supprimer la tâche
```

### Préparer le répertoire de restauration
Le script de restauration attend un **répertoire** (pas un `.zip`).
Décompressez l'archive si besoin :
```powershell
Expand-Archive -Path backups\jarvis-backup-AAAAmmjj_HHMMSS.zip -DestinationPath C:\temp\jarvis-restore
```

## 2. Lancer la restauration (script Python)

Le script : `scripts/restore_backup.py` (aucune dépendance externe).

### Vérifier d'abord (dry-run)
Liste ce qui serait restauré, **sans rien écrire** :
```powershell
python scripts/restore_backup.py C:\temp\jarvis-restore --dry-run
python scripts/restore_backup.py --dry-run        # utilise BACKUP_DIR par défaut
```

### Vérifier l'intégrité (--check)
Valide la présence des fichiers et la validité JSON. Renvoie un **code de sortie**
`0` (OK) ou `1` (échec) — pratique pour un script :
```powershell
python scripts/restore_backup.py C:\temp\jarvis-restore --check
if ($LASTEXITCODE -eq 0) { echo "Backup sain" } else { echo "Backup corrompu" }
```

### Restauration réelle
```powershell
python scripts/restore_backup.py C:\temp\jarvis-restore
```
- Restaure `memory/`, `logs/`, `config/` vers `J:\Projet JARVIS`.
- Les fichiers JSON sont écrits de façon **atomique** (`write_json_atomic`) pour éviter
  toute corruption.
- Une entrée est ajoutée dans `logs/restore.log`.

### Résolution du répertoire de backup
L'ordre de résolution est :
1. Argument positionnel `backup_dir`
2. Variable d'environnement `JARVIS_BACKUP_DIR`
3. `BACKUP_DIR` défini dans `scripts/schedule_backup.py` (par défaut `backups/`)

### Absence de backup
Si aucun répertoire de backup n'est trouvé, le script affiche une erreur explicite
et renvoie le code de sortie `1`.

## 3. Alternative PowerShell (legacy)
`scripts/restore.ps1` restaure directement depuis un `.zip` (demande le numéro
du backup si aucun fichier n'est précisé) :
```powershell
pwsh .\scripts\restore.ps1 -BackupFile backups\jarvis-backup-AAAAmmjj_HHMMSS.zip
```

## Résumé des codes de sortie
| Code | Signification |
|------|---------------|
| `0`  | Succès (restore OK, dry-run OK, ou check valide) |
| `1`  | Erreur (backup absent, intégrité invalide, ou exception) |
