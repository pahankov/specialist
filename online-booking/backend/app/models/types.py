"""Custom SQLAlchemy types."""
from datetime import timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class NaiveUTCDateTime(TypeDecorator):
    """Wall-clock datetime stored as a UTC instant and returned naive.

    asyncpg encodes a naive datetime for a timestamptz column using the
    process-local timezone, so 14:00 could become 11:00 UTC on a MSK host.
    Attaching UTC before bind keeps the wall-clock value stable regardless of
    the client or database timezone. Results are stripped back to naive
    because appointment/blocked-slot code compares them as local wall time.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None)
