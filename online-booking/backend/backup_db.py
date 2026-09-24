"""Backup SQLite database to SQL dump file.

Usage:
    python backup_db.py              # creates backups/db_YYYYMMDD_HHMMSS.sql
    python backup_db.py --keep 30    # delete backups older than 30 days
    python backup_db.py --compress   # create .sql.gz compressed backup
"""
import sys
import os
import gzip
import shutil
from pathlib import Path
from datetime import datetime


BACKUPS_DIR = Path(__file__).parent / "backups"
DB_PATH = Path(__file__).parent / "online_booking.db"


def create_backup(compress: bool = False) -> Path:
    """Create a backup of the database."""
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)
    
    BACKUPS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Try sqlite3 CLI first for SQL dump
    try:
        import subprocess
        result = subprocess.run(
            ["sqlite3", str(DB_PATH), ".dump"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0 and result.stdout:
            # SQL dump successful
            backup_path = BACKUPS_DIR / f"db_{timestamp}.sql"
            print(f"Backing up {DB_PATH} -> {backup_path}")
            backup_path.write_text(result.stdout, encoding="utf-8")
            
            if compress:
                compressed = backup_path.with_suffix(".sql.gz")
                with open(backup_path, "rb") as f_in:
                    with gzip.open(compressed, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_path.unlink()
                backup_path = compressed
                print(f"Compressed to {backup_path.name}")
            
            size = backup_path.stat().st_size
            print(f"Backup created: {size / 1024:.1f} KB")
            return backup_path
    except FileNotFoundError:
        pass  # sqlite3 CLI not available, fallback to .db copy
    
    # Fallback: copy .db file directly
    db_backup = BACKUPS_DIR / f"db_{timestamp}.db"
    print(f"sqlite3 CLI not found, copying .db file: {db_backup}")
    shutil.copy2(DB_PATH, db_backup)
    size = db_backup.stat().st_size
    print(f"Backup created: {size / 1024:.1f} KB")
    return db_backup


def cleanup_old_backups(days: int = 30):
    """Delete backups older than N days."""
    if not BACKUPS_DIR.exists():
        print("No backups directory found")
        return
    
    cutoff = datetime.now().timestamp() - (days * 86400)
    deleted = 0
    
    for f in BACKUPS_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
            print(f"Deleted old backup: {f.name}")
    
    print(f"Cleaned up {deleted} old backups")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backup SQLite database")
    parser.add_argument("--keep", type=int, default=None,
                       help="Delete backups older than N days")
    parser.add_argument("--compress", action="store_true",
                       help="Compress backup with gzip")
    parser.add_argument("--list", action="store_true",
                       help="List existing backups")
    
    args = parser.parse_args()
    
    if args.list:
        if BACKUPS_DIR.exists():
            print("Existing backups:")
            for f in sorted(BACKUPS_DIR.iterdir()):
                if f.is_file():
                    size = f.stat().st_size
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    print(f"  {f.name}  ({size / 1024:.1f} KB)  {mtime.strftime('%Y-%m-%d %H:%M')}")
        else:
            print("No backups found")
        sys.exit(0)
    
    if args.keep:
        cleanup_old_backups(args.keep)
    
    create_backup(compress=args.compress)
