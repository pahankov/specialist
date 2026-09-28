"""add_name_ru_to_countries

Revision ID: aaa7fcc30d47
Revises: f43f84fe3057
Create Date: 2026-09-28 19:20:36.581739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'aaa7fcc30d47'
down_revision: Union[str, None] = 'f43f84fe3057'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if column already exists (idempotent)
    result = conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'countries' AND column_name = 'name_ru'
            )
        """)
    )
    if result.scalar():
        # Column exists - just sync data
        try:
            conn.execute(text("UPDATE countries SET name_ru = name WHERE name_ru IS NULL OR name_ru = ''"))
        except Exception:
            pass
        return

    # Column doesn't exist - add it
    try:
        op.add_column('countries', sa.Column('name_ru', sa.String(100), nullable=True, server_default=''))
        try:
            conn.execute(text("UPDATE countries SET name_ru = name WHERE name_ru IS NULL OR name_ru = ''"))
        except Exception:
            pass
    except Exception:
        pass


def downgrade() -> None:
    op.drop_column('countries', 'name_ru')
