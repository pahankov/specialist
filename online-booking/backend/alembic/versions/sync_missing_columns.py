"""sync missing columns from models to database

Revision ID: sync_missing_columns
Revises: aaa7fcc30d47
Create Date: 2026-09-28 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'sync_missing_columns'
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
    # --- client_profiles: no_show_count ---
    if not _column_exists('client_profiles', 'no_show_count'):
        op.add_column('client_profiles', sa.Column('no_show_count', sa.Integer(), nullable=True, server_default='0'))

    # --- client_profiles: preferred_service_ids ---
    if not _column_exists('client_profiles', 'preferred_service_ids'):
        op.add_column('client_profiles', sa.Column('preferred_service_ids', sa.JSON(), nullable=True))

    # --- countries: name_ru ---
    if not _column_exists('countries', 'name_ru'):
        # Add as nullable first, then set default and sync data
        op.add_column('countries', sa.Column('name_ru', sa.String(100), nullable=True, server_default=''))
        try:
            op.execute("UPDATE countries SET name_ru = name WHERE name_ru IS NULL OR name_ru = ''")
        except Exception:
            pass

    # --- countries: name_en ---
    if not _column_exists('countries', 'name_en'):
        op.add_column('countries', sa.Column('name_en', sa.String(100), nullable=True, server_default=''))
        try:
            op.execute("UPDATE countries SET name_en = name WHERE name_en IS NULL OR name_en = ''")
        except Exception:
            pass


def downgrade() -> None:
    op.drop_column('client_profiles', 'preferred_service_ids')
    op.drop_column('client_profiles', 'no_show_count')
    op.drop_column('countries', 'name_en')
    op.drop_column('countries', 'name_ru')
