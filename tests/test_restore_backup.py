"""Tests du script de restauration de backup JARVIS."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.restore_backup as rb


def _make_fake_backup(backup_dir):
    """Cree un faux repertoire de backup avec 1 fichier JSON valide."""
    mem = os.path.join(backup_dir, "memory")
    os.makedirs(mem, exist_ok=True)
    conv = {"id": "c1", "messages": [{"role": "user", "content": "bonjour"}]}
    with open(os.path.join(mem, "conversation.json"), "w", encoding="utf-8") as f:
        json.dump(conv, f)
    return os.path.join(mem, "conversation.json")


def test_restore_restores_file(tmp_path):
    """Un fichier JSON valide du backup est bien restaure vers la destination."""
    backup_dir = tmp_path / "backup"
    _make_fake_backup(str(backup_dir))
    dest_root = tmp_path / "dest"

    restored = rb.restore(str(backup_dir), dest_root=str(dest_root), dry_run=False)

    assert len(restored) == 1
    dest_file = os.path.join(str(dest_root), "memory", "conversation.json")
    assert os.path.isfile(dest_file)
    with open(dest_file, encoding="utf-8") as f:
        assert json.load(f)["id"] == "c1"


def test_dry_run_does_nothing(tmp_path):
    """Le mode dry-run ne cree rien dans la destination."""
    backup_dir = tmp_path / "backup"
    _make_fake_backup(str(backup_dir))
    dest_root = tmp_path / "dest"

    restored = rb.restore(str(backup_dir), dest_root=str(dest_root), dry_run=True)

    assert restored == []
    assert not os.path.exists(os.path.join(str(dest_root), "memory", "conversation.json"))


def test_check_detects_invalid_json(tmp_path):
    """--check detecte un JSON invalide et renvoie ok=False."""
    backup_dir = tmp_path / "backup"
    mem = os.path.join(str(backup_dir), "memory")
    os.makedirs(mem, exist_ok=True)
    with open(os.path.join(mem, "bad.json"), "w", encoding="utf-8") as f:
        f.write("{ invalid json")

    ok, errors = rb.check_integrity(str(backup_dir))
    assert ok is False
    assert any("bad.json" in e for e in errors)


def test_missing_backup_raises(tmp_path):
    """restore leve FileNotFoundError si le backup est absent."""
    with pytest.raises(FileNotFoundError):
        rb.restore(str(tmp_path / "inexistant"))


def test_restore_snapshots_existing_destination(tmp_path):
    """B1 : restore() preserve l'etat courant via un snapshot avant ecrasement."""
    backup_dir = tmp_path / "backup"
    _make_fake_backup(str(backup_dir))
    dest_root = tmp_path / "dest"
    dest_mem = dest_root / "memory"
    dest_mem.mkdir(parents=True)
    live_file = dest_mem / "conversation.json"
    live_file.write_text(json.dumps({"id": "LIVE", "messages": []}), encoding="utf-8")

    rb.restore(str(backup_dir), dest_root=str(dest_root), dry_run=False)

    snapshots = list((dest_root / "backups" / "restore_snapshots").glob("*"))
    assert snapshots, "aucun snapshot cree"
    snapshot_file = (
        dest_root / "backups" / "restore_snapshots" / snapshots[0].name / "memory" / "conversation.json"
    )
    assert snapshot_file.is_file(), "fichier live non sauvegarde dans le snapshot"
    with open(snapshot_file, encoding="utf-8") as f:
        assert json.load(f)["id"] == "LIVE", "le snapshot doit contenir l'etat pre-restauration"
    with open(live_file, encoding="utf-8") as f:
        assert json.load(f)["id"] == "c1", "le live doit etre ecrase par le backup"


def test_restore_refuses_corrupt_backup(tmp_path):
    """B2 : restore() refuse un backup dont l'integrite echoue (fail-fast)."""
    backup_dir = tmp_path / "backup"
    mem = os.path.join(str(backup_dir), "memory")
    os.makedirs(mem, exist_ok=True)
    with open(os.path.join(mem, "bad.json"), "w", encoding="utf-8") as f:
        f.write("{ invalid json")

    with pytest.raises(ValueError, match="integrite"):
        rb.restore(str(backup_dir), dest_root=str(tmp_path / "dest"), dry_run=False)
