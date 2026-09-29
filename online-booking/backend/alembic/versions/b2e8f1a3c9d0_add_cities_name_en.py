"""add name_en to cities table

Revision ID: b2e8f1a3c9d0
Revises: sync_missing_columns
Create Date: 2026-09-29 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'b2e8f1a3c9d0'
down_revision: Union[str, None] = 'aaa7fcc30d47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if column exists in table."""
    conn = op.get_bind()
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


def upgrade() -> None:
    if not _column_exists('cities', 'name_en'):
        op.add_column('cities', sa.Column('name_en', sa.String(200), nullable=True, server_default=''))


def downgrade() -> None:
    op.drop_column('cities', 'name_en')
