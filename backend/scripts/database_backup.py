"""Create or verify-restore a Third-Hand SQLite database copy."""
from __future__ import annotations

import argparse

from app.database_maintenance import backup_database, restore_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up or restore a Third-Hand SQLite database")
    parser.add_argument("source", help="database to back up, or backup to restore")
    parser.add_argument("destination", help="new destination path; it must not already exist")
    parser.add_argument("--restore", action="store_true", help="copy a backup into a new restored database")
    args = parser.parse_args()
    operation = restore_database if args.restore else backup_database
    print(operation(args.source, args.destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
