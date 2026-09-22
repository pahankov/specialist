"""Migrate data from masters table to users + master_profiles

Revision ID: 0006_migrate_masters_to_users
Revises: 0005_add_user_model
Create Date: 2026-09-22

This migration copies data from the old 'masters' table into the new
'users' and 'master_profiles' tables, preserving all existing data.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006_migrate_masters_to_users'
down_revision: Union[str, None] = '0005_add_user_model'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migrate masters -> users (role=master or admin)
    op.execute("""
        INSERT INTO users (id, email, phone, hashed_password, name, role, is_active, is_admin, is_verified, created_at, updated_at)
        SELECT id, email, phone, hashed_password, name,
               CASE WHEN is_admin THEN 'admin' ELSE 'master' END,
               is_active, is_active, FALSE, created_at, updated_at
        FROM masters
    """)

    # Migrate masters -> master_profiles
    op.execute("""
        INSERT INTO master_profiles (user_id, description, avatar_url, telegram_username, is_active, created_at, updated_at)
        SELECT id, description, avatar_url, telegram_username, is_active, created_at, updated_at
        FROM masters
    """)


def downgrade() -> None:
    # This is a destructive downgrade - data will be lost
    # In production, you would need to reverse the migration carefully
    op.execute("DELETE FROM master_profiles")
    op.execute("DELETE FROM users WHERE role IN ('master', 'admin')")
