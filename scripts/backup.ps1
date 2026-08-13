<#
.SYNOPSIS
    Sauvegarde les donnees JARVIS (memory/, logs/, config/) dans une archive ZIP.

.DESCRIPTION
    Produit backups/jarvis-backup-YYYYMMDD_HHMMSS.zip contenant
    les repertoires memory/, logs/, config/.

    Utilisation :
        pwsh .\scripts\backup.ps1                     # archive dans backups/
        pwsh .\scripts\backup.ps1 -Destination C:\bak  # archive dans C:\bak\
        pwsh .\scripts\backup.ps1 -WhatIf              # dry-run sans ecrire

.PARAMETER Destination
    Repertoire de sortie (defaut: <ROOT>/backups).

.PARAMETER WhatIf
    Simule sans ecrire.
#>

param(
    [string]$Destination = "",
    [switch]$WhatIf = $false
)

$ErrorActionPreference = "Stop"
$ROOT = Resolve-Path "$PSScriptRoot\.."
$SUBDIRS = @("memory", "logs", "config")
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"

if (-not $Destination) {
    $Destination = Join-Path $ROOT "backups"
}

# Creer le repertoire de destination
if (-not (Test-Path $Destination)) {
    if ($WhatIf) { Write-Host "[dry-run] mkdir $Destination" }
    else { New-Item -ItemType Directory -Path $Destination -Force | Out-Null }
}

# Verifier qu'au moins un sous-dossier source existe
$hasData = $false
foreach ($sub in $SUBDIRS) {
    $src = Join-Path $ROOT $sub
    if (Test-Path $src) { $hasData = $true; break }
}
if (-not $hasData) {
    Write-Host "[INFO] Rien a sauvegarder (aucun des $($SUBDIRS -join ', ') trouve dans $ROOT)."
    exit 0
}

$ARCHIVE_NAME = "jarvis-backup-$TIMESTAMP.zip"
$ARCHIVE_PATH = Join-Path $Destination $ARCHIVE_NAME

$items = @()
foreach ($sub in $SUBDIRS) {
    $src = Join-Path $ROOT $sub
    if (Test-Path $src) { $items += $src }
}

if ($WhatIf) {
    Write-Host "[dry-run] Archive : $ARCHIVE_PATH"
    foreach ($item in $items) { Write-Host "  + $item" }
    Write-Host "[dry-run] $($items.Count) dossier(s) seraient archives."
    exit 0
}

Write-Host "[BACKUP] Creation de $ARCHIVE_PATH ..."
Compress-Archive -Path $items -DestinationPath $ARCHIVE_PATH -CompressionLevel Optimal
$size = (Get-Item $ARCHIVE_PATH).Length
Write-Host "[BACKUP] Termine : $ARCHIVE_PATH ($([math]::Round($size/1KB)) KB)"
