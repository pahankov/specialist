"""Add no_show_count to clients table

Revision ID: 0003_add_no_show_count
Revises: 0002_add_reviews
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_no_show_count'
down_revision: Union[str, None] = '0002_add_reviews'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clients',
        sa.Column('no_show_count', sa.Integer(), nullable=True, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('clients', 'no_show_count')
