"""Migrate data from clients table to users + client_profiles

Revision ID: 0007_migrate_clients_to_users
Revises: 0006_migrate_masters_to_users
Create Date: 2026-09-22

This migration copies data from the old 'clients' table into the new
'users' and 'client_profiles' tables, preserving all existing data.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007_migrate_clients_to_users'
down_revision: Union[str, None] = '0006_migrate_masters_to_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migrate clients -> users (role=client)
    op.execute("""
        INSERT INTO users (id, email, phone, hashed_password, name, role, is_active, is_verified, created_at, updated_at)
        SELECT id, email, phone, NULL, name, 'client', is_active, FALSE, created_at, updated_at
        FROM clients
    """)

    # Migrate clients -> client_profiles
    op.execute("""
        INSERT INTO client_profiles (user_id, no_show_count, created_at, updated_at)
        SELECT id, no_show_count, created_at, updated_at
        FROM clients
    """)


def downgrade() -> None:
    op.execute("DELETE FROM client_profiles")
    op.execute("DELETE FROM users WHERE role = 'client'")
