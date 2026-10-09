"""hot-path indexes for dashboard/listing aggregates

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-09

Counts and sums over appointments/users should not seq-scan as the tables
grow. IF NOT EXISTS everywhere: safe to re-run, SQLite-compatible.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_appointments_master_status_date", "appointments", "(master_id, status, appointment_date)"),
    ("ix_appointments_status_date", "appointments", "(status, appointment_date)"),
    ("ix_users_role", "users", "(role)"),
    ("ix_services_master", "services", "(master_id)"),
    ("ix_working_hours_master_date", "working_hours", "(master_id, schedule_date)"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, table, cols in _INDEXES:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} {cols}"))


def downgrade() -> None:
    conn = op.get_bind()
    for name, table, _cols in _INDEXES:
        conn.execute(text(f"DROP INDEX IF EXISTS {name}"))
