#!/usr/bin/env bash
# backup.sh — Sauvegarde les donnees JARVIS (memory/ logs/ config/) dans une archive .tar.gz
#
# Usage:
#   bash scripts/backup.sh                     # archive dans backups/
#   bash scripts/backup.sh /tmp/bak            # archive dans /tmp/bak/
#   bash scripts/backup.sh --dry-run           # simule sans ecrire
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUBDIRS=("memory" "logs" "config")
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${1:-$ROOT/backups}"
DRY_RUN=false

if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=true; DEST="${2:-$ROOT/backups}"; fi

mkdir -p "$DEST"

# Verifier qu'au moins un sous-dossier source existe
HAS_DATA=false
for sub in "${SUBDIRS[@]}"; do
  if [ -d "$ROOT/$sub" ]; then HAS_DATA=true; break; fi
done
if [ "$HAS_DATA" = false ]; then
  echo "[INFO] Rien a sauvegarder (aucun des ${SUBDIRS[*]} trouve dans $ROOT)."
  exit 0
fi

ARCHIVE_NAME="jarvis-backup-${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="$DEST/$ARCHIVE_NAME"

# Construire la liste des chemins a archiver
ITEMS=()
for sub in "${SUBDIRS[@]}"; do
  if [ -d "$ROOT/$sub" ]; then ITEMS+=("$ROOT/$sub"); fi
done

if [ "$DRY_RUN" = true ]; then
  echo "[dry-run] Archive : $ARCHIVE_PATH"
  for item in "${ITEMS[@]}"; do echo "  + $item"; done
  echo "[dry-run] ${#ITEMS[@]} dossier(s) seraient archives."
  exit 0
fi

echo "[BACKUP] Creation de $ARCHIVE_PATH ..."
tar -czf "$ARCHIVE_PATH" -C "$ROOT" "${SUBDIRS[@]}"
SIZE=$(stat -c%s "$ARCHIVE_PATH" 2>/dev/null || echo 0)
echo "[BACKUP] Termine : $ARCHIVE_PATH ($(( SIZE / 1024 )) KB)"
