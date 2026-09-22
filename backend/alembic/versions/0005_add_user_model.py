"""Add users, master_profiles, and client_profiles tables

Revision ID: 0005_add_user_model
Revises: 0004_add_countries_and_cities
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_add_user_model'
down_revision: Union[str, None] = '0004_add_countries_and_cities'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('role', sa.Enum('master', 'client', 'admin', name='userrole', create_type=True), nullable=False),
        sa.Column('city_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_phone', 'users', ['phone'], unique=True)
    op.create_index('ix_users_role', 'users', ['role'])

    # Create master_profiles table
    op.create_table(
        'master_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('telegram_username', sa.String(100), nullable=True),
        sa.Column('experience_years', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    # Create client_profiles table
    op.create_table(
        'client_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('no_show_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('preferred_service_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('client_profiles')
    op.drop_table('master_profiles')
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_phone', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS userrole")
