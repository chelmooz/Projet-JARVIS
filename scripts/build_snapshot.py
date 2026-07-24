"""Snapshot SHA256 de l'environnement JARVIS + rollback.

Golden-image légère : hash SHA256 de l'environnement déployé
(portable_python + bin + venv + config + models) pour un déploiement
reproductible et un rollback propre sur clef USB. Réutilise
``services.ollama_installer._sha256_of`` (déjà testé sur le binaire Ollama).

Usage:
    python scripts/build_snapshot.py create                 # manifest sous snapshots/
    python scripts/build_snapshot.py create --archive        # + archive env.zip
    python scripts/build_snapshot.py create --no-models     # exclut les GGUF
    python scripts/build_snapshot.py restore SNAP           # verifie + restore (1 cmd)
    python scripts/build_snapshot.py restore SNAP --check   # verify only (exit code)
    python scripts/build_snapshot.py restore SNAP --dry-run # liste sans ecrire
"""
import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config.paths as paths
from services.file_utils import write_json_atomic
from services.ollama_installer import _sha256_of

_logger = logging.getLogger(__name__)

# Racines de l'environnement déployé (relatives a ROOT).
DEFAULT_ROOTS = ["portable_python", "bin", "venv", "config", "models"]
SNAPSHOT_DIR = os.path.join(paths.ROOT, "snapshots")
MANIFEST_NAME = "snapshot_manifest.json"
ARCHIVE_NAME = "env.zip"
TOOL_VERSION = "1.0"


def _git_head(base: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=base, stderr=subprocess.DEVNULL
        ).decode().strip() or None
    except Exception:
        _logger.warning("Impossible de lire le HEAD git dans %s", base)
        return None


def iter_files(roots: list[str], base: str):
    """Yield les chemins absolus des fichiers présents sous chaque racine."""
    for r in roots:
        d = os.path.join(base, r)
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for name in files:
                yield os.path.join(root, name)


def build_manifest(base: str, roots: list[str], version: str | None = None) -> dict:
    """Construit le manifest SHA256 de l'environnement."""
    version = version or _git_head(base) or "unknown"
    entries = []
    for f in iter_files(roots, base):
        rel = os.path.relpath(f, base)
        entries.append({
            "path": rel,
            "sha256": _sha256_of(f),
            "size": os.path.getsize(f),
        })
    return {
        "tool": "jarvis-snapshot",
        "tool_version": TOOL_VERSION,
        "version": version,
        "created_at": datetime.datetime.now().isoformat(),
        "base": base,
        "roots": roots,
        "entries": entries,
    }


def verify_manifest(manifest: dict, base: str) -> list[tuple[str, str]]:
    """Retourne la liste de dérives (path, 'missing'|'mismatch')."""
    drift: list[tuple[str, str]] = []
    for e in manifest["entries"]:
        p = os.path.join(base, e["path"])
        if not os.path.exists(p):
            drift.append((e["path"], "missing"))
            continue
        if _sha256_of(p) != e["sha256"]:
            drift.append((e["path"], "mismatch"))
    return drift


def create_archive(manifest: dict, base: str, archive_path: str) -> None:
    """Archive l'environnement (bytes) pour un rollback complet."""
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as z:
        for e in manifest["entries"]:
            z.write(os.path.join(base, e["path"]), e["path"])


def restore_from_archive(manifest: dict, base: str, archive_path: str,
                         dry_run: bool = False) -> list[str]:
    """Restaure les fichiers déviants depuis l'archive. Retourne les chemins restaurés."""
    restored: list[str] = []
    with zipfile.ZipFile(archive_path) as z:
        for e in manifest["entries"]:
            p = os.path.join(base, e["path"])
            if os.path.exists(p) and _sha256_of(p) == e["sha256"]:
                continue
            restored.append(e["path"])
            if dry_run:
                continue
            z.extract(e["path"], base)
    return restored


def cmd_create(args: argparse.Namespace) -> int:
    roots = [r for r in DEFAULT_ROOTS if r != "models"] if args.no_models else list(DEFAULT_ROOTS)
    missing = [r for r in roots if not os.path.isdir(os.path.join(paths.ROOT, r))]
    if missing:
        print(f"[warn] racines absentes (ignorees) : {', '.join(missing)}")
    manifest = build_manifest(paths.ROOT, roots)
    out_dir = args.output or os.path.join(
        SNAPSHOT_DIR, datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, MANIFEST_NAME)
    write_json_atomic(manifest_path, manifest, indent=2)
    total = sum(e["size"] for e in manifest["entries"])
    print(f"Snapshot: {manifest_path}")
    print(f"  racines : {', '.join(roots)}")
    print(f"  fichiers: {len(manifest['entries'])}  ({total / 1e6:.1f} Mo)")
    print(f"  version : {manifest['version']}")
    if args.archive:
        archive_path = os.path.join(out_dir, ARCHIVE_NAME)
        create_archive(manifest, paths.ROOT, archive_path)
        print(f"  archive : {archive_path}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    snap_dir = args.snapshot
    manifest_path = os.path.join(snap_dir, MANIFEST_NAME)
    if not os.path.exists(manifest_path):
        print(f"[erreur] manifest introuvable : {manifest_path}", file=sys.stderr)
        return 2
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    target = args.target or manifest.get("base") or paths.ROOT
    drift = verify_manifest(manifest, target)
    if not drift:
        print("Integrite OK — aucune derive.")
        return 0
    print(f"Derive detectee sur {len(drift)} fichier(s) :")
    for path, kind in drift:
        print(f"  - {path} ({kind})")
    archive_path = args.archive or os.path.join(snap_dir, ARCHIVE_NAME)
    if args.check:
        return 1
    if not os.path.exists(archive_path):
        print("[erreur] archive absente — impossible de restaurer (utilisez --archive)",
              file=sys.stderr)
        return 1
    restored = restore_from_archive(manifest, target, archive_path, dry_run=args.dry_run)
    if args.dry_run:
        print(f"[dry-run] {len(restored)} fichier(s) a restaurer.")
    else:
        print(f"Restaure : {len(restored)} fichier(s).")
        remaining = verify_manifest(manifest, target)
        if remaining:
            print(f"[erreur] derive persistante : {len(remaining)} fichier(s)", file=sys.stderr)
            return 1
        print("Integrite re-etablie.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot SHA256 + rollback JARVIS")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="construit un manifest SHA256 de l'environnement")
    c.add_argument("--output", default=None, help="repertoire de sortie du snapshot")
    c.add_argument("--no-models", action="store_true", help="exclut les GGUF (models/)")
    c.add_argument("--archive", action="store_true", help="ajoute une archive env.zip")
    c.set_defaults(func=cmd_create)
    r = sub.add_parser("restore", help="verifie/restaure depuis un snapshot")
    r.add_argument("snapshot", help="repertoire du snapshot")
    r.add_argument("--archive", default=None, help="archive env.zip (sinon cherchee dans le snapshot)")
    r.add_argument("--target", default=None, help="racine de restauration (defaut: manifest.base)")
    r.add_argument("--dry-run", action="store_true", help="liste sans ecrire")
    r.add_argument("--check", action="store_true", help="verifie seulement (exit code)")
    r.set_defaults(func=cmd_restore)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
