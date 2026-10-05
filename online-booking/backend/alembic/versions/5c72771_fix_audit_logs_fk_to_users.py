"""fix audit_logs FK to users

Revision ID: 5c72771
Revises: 4fdb5e791ead
Create Date: 2026-09-30

Change audit_logs.master_id FK from master_profiles to users
so that admins (who don't have MasterProfile) can log actions.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c72771'
down_revision = '4fdb5e791ead'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Grant ownership to fix permission issues (table was created by postgres user)
    try:
        conn.execute(sa.text("GRANT ALL ON audit_logs TO current_user"))
    except Exception:
        pass  # Already owned or insufficient privileges
    
    # Drop old FK constraint
    op.drop_constraint('audit_logs_master_id_fkey', 'audit_logs', type_='foreignkey')
    
    # Add new FK to users table
    op.create_foreign_key(
        'audit_logs_master_id_fkey',
        'audit_logs', 'users',
        ['master_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Revert FK to master_profiles
    op.drop_constraint('audit_logs_master_id_fkey', 'audit_logs', type_='foreignkey')
    
    op.create_foreign_key(
        'audit_logs_master_id_fkey',
        'audit_logs', 'master_profiles',
        ['master_id'], ['id']
    )
