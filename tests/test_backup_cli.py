import json
import os
import sqlite3
import subprocess
import sys

import pytest

from academia.db import backup_bytes, full_export, restore_backup
from academia.models import parse_bundle
from academia.service import Academy


def test_backup_restores_all_state_including_reviews(populated, instant, tmp_path):
    populated.review(1, "Mi respuesta", 3, errors="Nota de error", at=instant)
    populated.expose(1, "comprendido", "Nota personal", at=instant)
    snapshot = full_export(populated.path)
    backup = tmp_path / "backup.sqlite3"
    backup.write_bytes(backup_bytes(populated.path))
    restored = tmp_path / "restored.sqlite3"
    restore_backup(backup, restored)
    assert json.loads(full_export(restored)) == json.loads(snapshot)
    assert Academy(restored).tasks(due_only=False)[0]["version"] == 1
    with pytest.raises(ValueError, match="ya existe"):
        restore_backup(backup, restored)


def test_session_export_reimports_without_importing_mastery(populated, instant, tmp_path):
    populated.review(1, "respuesta", 4, at=instant)
    portable = parse_bundle(populated.export_sessions())
    target = Academy(tmp_path / "portable.sqlite3")
    target.import_bundle(portable)
    assert len(target.detail(1)["evidence"]) == 1
    assert target.detail(1)["reviews"] == []


def test_future_database_version_is_never_overwritten(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="más reciente"):
        Academy(path)


def test_restore_rejects_incomplete_or_foreign_db(tmp_path):
    bad = tmp_path / "bad.sqlite3"
    with sqlite3.connect(bad) as conn:
        conn.execute("PRAGMA user_version=1")
    with pytest.raises(ValueError, match="esquema completo"):
        restore_backup(bad, tmp_path / "destination.sqlite3")
    assert not (tmp_path / "destination.sqlite3").exists()


def test_export_preserves_original_and_fsrs_logs(populated, instant):
    populated.review(1, "respuesta", 2, at=instant)
    export = json.loads(full_export(populated.path))
    assert export["format"] == "mi-academia-export"
    assert export["tables"]["sessions"][0]["original_text"]
    assert export["tables"]["reviews"][0]["scheduler_json"]
    assert export["tables"]["reviews"][0]["evaluator"] == "self"


def test_cli_dry_run_import_backup_restore(tmp_path):
    db = tmp_path / "cli.sqlite3"
    env = dict(os.environ, PYTHONUTF8="1")
    def cli(*args, target=db):
        return subprocess.run([sys.executable, "-m", "academia.cli", "--db", str(target), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", env=env)
    result = cli("import", "examples/sesion.json", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert Academy(db).sessions() == []
    assert cli("import", "examples/sesion.json").returncode == 0
    backup = tmp_path / "cli-backup.sqlite3"
    assert cli("backup", backup).returncode == 0
    target = tmp_path / "cli-restored.sqlite3"
    assert cli("restore", backup, target=target).returncode == 0
    assert len(Academy(target).list_knowledge()) == 4
    assert cli("restore", backup, target=target).returncode != 0
