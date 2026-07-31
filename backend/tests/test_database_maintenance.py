import sqlite3

import pytest

from app.database_maintenance import backup_database, restore_database
from app.migrations import run_migrations
from app.storage import PortfolioStore


def test_migration_runner_is_idempotent(tmp_path):
    database = tmp_path / "third-hand.db"
    PortfolioStore(database)

    assert run_migrations(database) == ["0001_legacy_schema_baseline"]
    assert run_migrations(database) == []
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT migration_id FROM schema_migrations").fetchall() == [
            ("0001_legacy_schema_baseline",)
        ]


def test_backup_and_restore_preserve_data_without_overwriting_targets(tmp_path):
    source, backup, restored = tmp_path / "source.db", tmp_path / "backup.db", tmp_path / "restored.db"
    store = PortfolioStore(source)
    store.save_available_cash(1234.5)

    assert backup_database(source, backup) == backup
    assert restore_database(backup, restored) == restored
    assert PortfolioStore(restored).available_cash()["available_cash"] == 1234.5
    with pytest.raises(FileExistsError):
        backup_database(source, backup)
