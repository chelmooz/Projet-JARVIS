"""Restaure les donnees JARVIS a partir d'un repertoire de backup.

Le backup est un repertoire contenant les sous-dossiers : memory/, logs/, config/.
(Il peut provenir d'un dezip de backups/jarvis-backup-*.zip ou d'un backup manuel.)

Usage:
    python scripts/restore_backup.py                         # restaure depuis BACKUP_DIR
    python scripts/restore_backup.py C:/chemin/backup        # restaure depuis un dossier
    python scripts/restore_backup.py --dry-run               # liste sans ecrire
    python scripts/restore_backup.py --check                 # verifie l'integrite (exit code)
"""
import argparse
import datetime
import json
import os
import shutil
import sys

# Import du projet (ROOT, chemins) sans hardcoder
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config.paths as paths
from services.file_utils import read_json, write_json_atomic

# Sous-dossiers restaures vers la racine du projet
SOURCE_SUBDIRS = ["memory", "logs", "config"]

# Variables d'environnement permettant de surcharger le repertoire de backup
BACKUP_ENV = "JARVIS_BACKUP_DIR"


def get_backup_dir(arg: str | None = None) -> str:
    """Resout le repertoire de backup : argument > env > BACKUP_DIR de schedule_backup."""
    if arg:
        return os.path.abspath(arg)
    env = os.environ.get(BACKUP_ENV)
    if env:
        return os.path.abspath(env)
    try:
        from scripts.schedule_backup import BACKUP_DIR
        return BACKUP_DIR
    except Exception:
        return os.path.join(paths.ROOT, "backups")


def list_backup_items(backup_dir: str, dest_root: str | None = None) -> list[tuple[str, str]]:
    """Retourne la liste des paires (chemin_source, chemin_destination) a restaurer."""
    dest_root = dest_root or paths.ROOT
    items: list[tuple[str, str]] = []
    for sub in SOURCE_SUBDIRS:
        src = os.path.join(backup_dir, sub)
        if not os.path.isdir(src):
            continue
        for root, _dirs, files in os.walk(src):
            for name in files:
                s = os.path.join(root, name)
                rel = os.path.relpath(s, backup_dir)
                d = os.path.join(dest_root, rel)
                items.append((s, d))
    return items


def check_integrity(backup_dir: str) -> tuple[bool, list[str]]:
    """Verifie l'integrite : fichiers presents et JSON valides. Renvoie (ok, messages)."""
    errors: list[str] = []
    items = list_backup_items(backup_dir)
    if not items:
        return False, ["Aucun fichier a restaurer dans le backup."]
    for s, _d in items:
        if s.lower().endswith(".json"):
            try:
                with open(s, encoding="utf-8") as f:
                    json.load(f)
            except (OSError, json.JSONDecodeError):
                errors.append(f"JSON invalide ou illisible : {s}")
    return (len(errors) == 0, errors)


def _write_restore_log(dest_root: str, backup_dir: str, restored: list[str]) -> None:
    """Ecrit une entree de journal dans logs/restore.log (non atomique : append)."""
    log_dir = os.path.join(dest_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "restore.log")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] RESTAURE {len(restored)} fichier(s) depuis {backup_dir}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def snapshot_dest(dest_root: str) -> str | None:
    """Sauvegarde l'etat courant de SOURCE_SUBDIRS avant restauration.

    Cree `backups/restore_snapshots/<timestamp>/` et y copie les fichiers existants
    de memory/, logs/, config/. Renvoie le chemin du snapshot, ou None si rien
    a sauvegarder (destination vide). En cas d'erreur disque, leve pour bloquer
    la restauration (fail-fast : mieux vaut refuser que perdre l'etat courant).
    """
    dest_root = dest_root or paths.ROOT
    srcs = [os.path.join(dest_root, sub) for sub in SOURCE_SUBDIRS]
    if not any(os.path.isdir(s) for s in srcs):
        return None
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_root = os.path.join(dest_root, "backups", "restore_snapshots", stamp)
    copied = 0
    for sub in SOURCE_SUBDIRS:
        src = os.path.join(dest_root, sub)
        if not os.path.isdir(src):
            continue
        for root, _dirs, files in os.walk(src):
            for name in files:
                s = os.path.join(root, name)
                rel = os.path.relpath(s, dest_root)
                d = os.path.join(snap_root, rel)
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
                copied += 1
    return snap_root if copied else None


def restore(
    backup_dir: str,
    dest_root: str | None = None,
    dry_run: bool = False,
    no_snapshot: bool = False,
    skip_integrity: bool = False,
) -> list[str]:
    """Restaure les fichiers du backup vers dest_root. Renvoie la liste des fichiers restaures.

    En mode dry_run, ne copie/ecrit rien et renvoie une liste vide.
    Avant ecriture, verifie l'integrite du backup (fail-fast si corrompu) et,
    sauf no_snapshot, sauvegarde l'etat courant de la destination (reversible).
    """
    dest_root = dest_root or paths.ROOT
    if not os.path.isdir(backup_dir):
        raise FileNotFoundError(f"Repertoire de backup introuvable : {backup_dir}")

    if not skip_integrity:
        ok, errors = check_integrity(backup_dir)
        if not ok:
            raise ValueError(
                f"Restauration refusee : integrite du backup invalide ({len(errors)} erreur(s))"
            )

    if not no_snapshot and not dry_run:
        snapshot_dest(dest_root)

    items = list_backup_items(backup_dir, dest_root)
    restored: list[str] = []
    for s, d in items:
        if dry_run:
            print(f"  [dry-run] {s} -> {d}")
            continue
        os.makedirs(os.path.dirname(d), exist_ok=True)
        # Ecriture atomique pour les JSON afin d'eviter toute corruption
        if d.lower().endswith(".json") and os.path.getsize(s) > 0:
            data = read_json(s)
            write_json_atomic(d, data)
        else:
            shutil.copy2(s, d)
        restored.append(d)

    if not dry_run and restored:
        _write_restore_log(dest_root, backup_dir, restored)
    return restored


def main() -> int:
    """Point d'entree CLI. Renvoie un code de sortie (0 ok, 1 erreur)."""
    parser = argparse.ArgumentParser(description="Restaure les donnees JARVIS depuis un backup")
    parser.add_argument("backup_dir", nargs="?", default=None, help="Repertoire de backup (defaut: BACKUP_DIR)")
    parser.add_argument("--dry-run", action="store_true", help="Liste sans rien ecrire")
    parser.add_argument("--check", action="store_true", help="Verifie l'integrite et quitte")
    args = parser.parse_args()

    backup_dir = get_backup_dir(args.backup_dir)

    if not os.path.isdir(backup_dir):
        print(f"[ERREUR] Aucun backup trouve : {backup_dir}")
        return 1

    if args.check:
        ok, errors = check_integrity(backup_dir)
        if ok:
            n = len(list_backup_items(backup_dir))
            print(f"[OK] Integrite du backup validee ({n} fichier(s)).")
            return 0
        for e in errors:
            print(f"[ERREUR] {e}")
        print("[ERREUR] Integrite du backup invalide.")
        return 1

    if args.dry_run:
        items = list_backup_items(backup_dir)
        if not items:
            print("[INFO] Rien a restaurer (backup vide ou inconnu).")
            return 0
        print(f"[dry-run] {len(items)} fichier(s) serai(en)t restaure(s) vers {paths.ROOT} :")
        for s, d in items:
            print(f"  {s} -> {d}")
        return 0

    restored = restore(backup_dir)
    if not restored:
        print("[INFO] Rien a restaurer (backup vide ou inconnu).")
        return 0
    print(f"[OK] {len(restored)} fichier(s) restaure(s) vers {paths.ROOT}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
