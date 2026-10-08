"""master tariffs with 6-month trial

Revision ID: e7a1c2d4b5f6
Revises: 5c72771
Create Date: 2026-10-08

Billing foundation (no charges yet): every master sits on a tariff.
Existing masters get trial retroactively: trial_ends_at = now + 180 days.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'e7a1c2d4b5f6'
down_revision: Union[str, None] = '5c72771'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
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
    if not _column_exists('master_profiles', 'tariff'):
        op.add_column(
            'master_profiles',
            sa.Column('tariff', sa.String(20), nullable=False, server_default='trial'),
        )
    if not _column_exists('master_profiles', 'trial_ends_at'):
        op.add_column(
            'master_profiles',
            sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        )
    # Retroactive trial for existing masters: 6 months from now
    op.execute(
        text("UPDATE master_profiles SET trial_ends_at = now() + interval '180 days' "
             "WHERE trial_ends_at IS NULL")
    )


def downgrade() -> None:
    op.drop_column('master_profiles', 'trial_ends_at')
    op.drop_column('master_profiles', 'tariff')
