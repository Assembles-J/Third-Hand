"""Safe, SQLite-native backup and restore helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def _copy_database(source: str | Path, destination: str | Path) -> Path:
    source_path, destination_path = Path(source), Path(destination)
    if not source_path.is_file():
        raise FileNotFoundError(f"database does not exist: {source_path}")
    if destination_path.exists():
        raise FileExistsError(f"destination already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(source_path) as source_connection, sqlite3.connect(destination_path) as destination_connection:
            source_connection.backup(destination_connection)
        with sqlite3.connect(destination_path) as check_connection:
            integrity = str(check_connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise RuntimeError(f"backup integrity check failed: {integrity}")
    except Exception:
        if destination_path.exists():
            destination_path.unlink()
        raise
    return destination_path


def backup_database(source: str | Path, destination: str | Path) -> Path:
    """Create a verified backup without overwriting an existing file."""
    return _copy_database(source, destination)


def restore_database(backup: str | Path, destination: str | Path) -> Path:
    """Restore a verified backup to a new destination without overwriting it."""
    return _copy_database(backup, destination)
