"""UTC timezone utilities.

All datetime operations MUST use these helpers to ensure consistent UTC storage.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """Return current UTC datetime without timezone info (for SQLite).

    SQLite doesn't store timezone info, so we strip it after setting to UTC.
    """
    return utcnow().replace(tzinfo=None)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC-aware.

    If naive (no tzinfo), assume it's UTC and attach timezone.
    If already aware, convert to UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
