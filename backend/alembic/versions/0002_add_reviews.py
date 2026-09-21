"""Add reviews table

Revision ID: 0002_add_reviews
Revises: initial
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_add_reviews'
down_revision: Union[str, None] = 'initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('master_id', sa.Integer(), nullable=False),
        sa.Column('client_name', sa.String(length=100), nullable=False),
        sa.Column('client_phone', sa.String(length=20), nullable=False),
        sa.Column('rating', sa.Float(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['master_id'], ['masters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('appointment_id')
    )
    op.create_index('ix_reviews_appointment_id', 'reviews', ['appointment_id'])
    op.create_index('ix_reviews_master_id', 'reviews', ['master_id'])
    op.create_index('ix_reviews_master_published', 'reviews', ['master_id', 'is_published'])


def downgrade() -> None:
    op.drop_index('ix_reviews_master_published', table_name='reviews')
    op.drop_index('ix_reviews_master_id', table_name='reviews')
    op.drop_index('ix_reviews_appointment_id', table_name='reviews')
    op.drop_table('reviews')
