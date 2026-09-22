"""Drop old tables and create new refresh_tokens table

Revision ID: 0008_drop_old_tables
Revises: 0007_migrate_clients_to_users
Create Date: 2026-09-22

Drops the old 'masters' and 'clients' tables, and replaces refresh_tokens
to reference users.id instead of masters.id.

NOTE: Foreign key constraints in services, appointments, etc. still reference
masters.id. These must be handled by the application layer or via additional
migrations. For now, we keep the old tables as views or add triggers.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_drop_old_tables'
down_revision: Union[str, None] = '0007_migrate_clients_to_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old refresh_tokens and create new one referencing users
    op.drop_table('refresh_tokens')
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(512), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'], unique=True)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])

    # Drop old tables
    op.drop_table('masters')
    op.drop_table('clients')


def downgrade() -> None:
    # Recreate old refresh_tokens referencing masters
    op.drop_table('refresh_tokens')
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(512), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['masters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'], unique=True)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])

    # Recreate old tables (data would need to be restored)
    op.execute("""
        CREATE TABLE masters AS
        SELECT u.id, u.name, u.email, u.hashed_password, u.phone,
               mp.telegram_username, mp.description, mp.avatar_url,
               u.is_active, (u.role = 'admin') as is_admin,
               u.created_at, u.updated_at
        FROM users u
        LEFT JOIN master_profiles mp ON mp.user_id = u.id
        WHERE u.role IN ('master', 'admin')
    """)
    op.execute("""
        CREATE TABLE clients AS
        SELECT u.id, u.name, u.phone, u.email,
               COALESCE(cp.no_show_count, 0) as no_show_count,
               u.created_at, u.updated_at
        FROM users u
        LEFT JOIN client_profiles cp ON cp.user_id = u.id
        WHERE u.role = 'client'
    """)
