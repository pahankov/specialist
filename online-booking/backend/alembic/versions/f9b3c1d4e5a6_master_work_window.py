"""master daily work window (work_start_hour/work_end_hour)

Revision ID: f9b3c1d4e5a6
Revises: e7a1c2d4b5f6
Create Date: 2026-10-09

Schedule granules render for [work_start_hour, work_end_hour).
Defaults 8-22 preserve current behaviour.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'f9b3c1d4e5a6'
down_revision: Union[str, None] = 'e7a1c2d4b5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    try:
        result = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = :t AND column_name = :c
                )
            """),
            {"t": table, "c": column}
        )
        return result.scalar()
    except Exception:
        cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(c[1] == column for c in cols)


def upgrade() -> None:
    if not _column_exists('master_profiles', 'work_start_hour'):
        op.add_column(
            'master_profiles',
            sa.Column('work_start_hour', sa.Integer(), nullable=False, server_default='8'),
        )
    if not _column_exists('master_profiles', 'work_end_hour'):
        op.add_column(
            'master_profiles',
            sa.Column('work_end_hour', sa.Integer(), nullable=False, server_default='22'),
        )


def downgrade() -> None:
    op.drop_column('master_profiles', 'work_end_hour')
    op.drop_column('master_profiles', 'work_start_hour')
