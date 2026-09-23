"""Restore database from backup.

Usage:
    python restore_db.py latest              # restore from most recent backup
    python restore_db.py backups/db_20260923.sql
    python restore_db.py --force             # skip confirmation

WARNING: This will REPLACE the current database!
"""
import sys
import os
import gzip
import shutil
from pathlib import Path
from datetime import datetime


BACKUPS_DIR = Path(__file__).parent / "backups"
DB_PATH = Path(__file__).parent / "online_booking.db"


def list_backups():
    """List available backups."""
    if not BACKUPS_DIR.exists():
        print("No backups directory found")
        return []
    
    backups = sorted(BACKUPS_DIR.iterdir())
    result = []
    for f in backups:
        if f.is_file() and (f.suffix in (".sql", ".sql.gz", ".db")):
            size = f.stat().st_size
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            result.append(f)
            print(f"  [{len(result)}] {f.name}  ({size / 1024:.1f} KB)  {mtime.strftime('%Y-%m-%d %H:%M')}")
    
    return result


def restore_from_sql(backup_path: Path, force: bool = False):
    """Restore database from SQL dump."""
    if not force:
        confirm = input(f"\n⚠️  WARNING: This will REPLACE {DB_PATH}\n"
                       f"Type 'YES' to confirm: ")
        if confirm != "YES":
            print("Cancelled")
            sys.exit(0)
    
    # Backup current DB before restore
    if DB_PATH.exists():
        backup_current = BACKUPS_DIR / f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        print(f"Saving current DB to {backup_current}")
        shutil.copy2(DB_PATH, backup_current)
    
    # Restore
    print(f"Restoring from {backup_path}")
    
    import subprocess
    result = subprocess.run(
        ["sqlite3", str(DB_PATH)],
        input=backup_path.read_text(encoding="utf-8"),
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print("✅ Database restored successfully!")
    else:
        print(f"❌ Restore failed: {result.stderr}")
        sys.exit(1)


def restore_from_db(backup_path: Path, force: bool = False):
    """Restore from .db file copy."""
    if not force:
        confirm = input(f"\n⚠️  WARNING: This will REPLACE {DB_PATH}\n"
                       f"Type 'YES' to confirm: ")
        if confirm != "YES":
            print("Cancelled")
            sys.exit(0)
    
    print(f"Restoring from {backup_path}")
    shutil.copy2(backup_path, DB_PATH)
    print("✅ Database restored successfully!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Restore database from backup")
    parser.add_argument("backup", nargs="?", default="latest",
                       help="Backup file path or 'latest'")
    parser.add_argument("--force", action="store_true",
                       help="Skip confirmation")
    parser.add_argument("--list", action="store_true",
                       help="List available backups")
    
    args = parser.parse_args()
    
    if args.list:
        list_backups()
        sys.exit(0)
    
    # Find backup file
    if args.backup == "latest":
        backups = list(list_backups())
        if not backups:
            print("No backups found!")
            sys.exit(1)
        backup_path = backups[-1]
        print(f"\nUsing latest backup: {backup_path.name}")
    else:
        backup_path = Path(args.backup)
        if not backup_path.exists():
            print(f"ERROR: Backup file not found: {backup_path}")
            sys.exit(1)
    
    # Restore based on file type
    if backup_path.suffix == ".sql":
        restore_from_sql(backup_path, args.force)
    elif backup_path.suffix == ".gz":
        # Decompress first
        temp_sql = Path(str(backup_path) + ".sql")
        print(f"Decompressing {backup_path.name}...")
        with gzip.open(backup_path, "rb") as f_in:
            with open(temp_sql, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        try:
            restore_from_sql(temp_sql, args.force)
        finally:
            temp_sql.unlink()
    elif backup_path.suffix == ".db":
        restore_from_db(backup_path, args.force)
    else:
        print(f"Unsupported file type: {backup_path.suffix}")
        sys.exit(1)
