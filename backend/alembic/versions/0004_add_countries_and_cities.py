"""Add countries and cities tables

Revision ID: 0004_add_countries_and_cities
Revises: 0003_add_no_show_count
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_add_countries_and_cities'
down_revision: Union[str, None] = '0003_add_no_show_count'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create countries table
    op.create_table(
        'countries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(3), nullable=False),
        sa.Column('name_ru', sa.String(100), nullable=False),
        sa.Column('name_en', sa.String(100), nullable=False),
        sa.Column('phone_prefix', sa.String(10), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_countries_code', 'countries', ['code'], unique=True)

    # Create cities table
    op.create_table(
        'cities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('country_id', sa.Integer(), nullable=False),
        sa.Column('name_ru', sa.String(200), nullable=False),
        sa.Column('name_en', sa.String(200), nullable=True),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.ForeignKeyConstraint(['country_id'], ['countries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cities_country_slug', 'cities', ['country_id', 'slug'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_cities_country_slug', table_name='cities')
    op.drop_table('cities')
    op.drop_index('ix_countries_code', table_name='countries')
    op.drop_table('countries')
