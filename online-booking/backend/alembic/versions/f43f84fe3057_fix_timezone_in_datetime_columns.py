"""fix timezone in datetime columns and clean up removed tables

Revision ID: f43f84fe3057
Revises: 08fbbef38349
Create Date: 2026-09-28 11:09:14.003657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f43f84fe3057'
down_revision: Union[str, None] = '08fbbef38349'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe_drop_table(table_name: str) -> None:
    """Drop table if exists without requiring ownership."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')")
    )
    exists = result.scalar()
    if exists:
        try:
            conn.execute(sa.text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        except Exception:
            pass


def upgrade() -> None:
    conn = op.get_bind()

    # --- Clean up removed tables ---
    _safe_drop_table('locations')
    _safe_drop_table('social_accounts')

    # --- Clean up removed columns from client_profiles ---
    for col in ['location_lat', 'location_lon', 'preferred_location']:
        try:
            conn.execute(sa.text(f"ALTER TABLE client_profiles DROP COLUMN IF EXISTS {col}"))
        except Exception:
            pass

    # --- Clean up removed columns from master_profiles ---
    for col in ['cabinet_lat', 'cabinet_lon', 'cabinet_address']:
        try:
            conn.execute(sa.text(f"ALTER TABLE master_profiles DROP COLUMN IF EXISTS {col}"))
        except Exception:
            pass

    # --- Clean up removed columns/index from users ---
    try:
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_telegram_user_id"))
    except Exception:
        pass
    try:
        conn.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS telegram_user_id"))
    except Exception:
        pass

    # --- Fix timezone in DateTime columns (PostgreSQL) ---
    # Use direct SQL ALTER TABLE to avoid batch_alter_table ownership requirement
    timezone_alters = [
        # (table, column)
        ('users', 'created_at'),
        ('users', 'updated_at'),
        ('appointments', 'appointment_date'),
        ('appointments', 'created_at'),
        ('appointments', 'updated_at'),
        ('client_profiles', 'created_at'),
        ('client_profiles', 'updated_at'),
        ('master_profiles', 'created_at'),
        ('master_profiles', 'updated_at'),
        ('services', 'created_at'),
        ('services', 'updated_at'),
        ('working_hours', 'created_at'),
        ('working_hours', 'updated_at'),
        ('audit_logs', 'created_at'),
        ('blocked_slots', 'start_dt'),
        ('blocked_slots', 'end_dt'),
        ('blocked_slots', 'created_at'),
        ('blocked_slots', 'updated_at'),
        ('refresh_tokens', 'expires_at'),
        ('refresh_tokens', 'revoked_at'),
        ('refresh_tokens', 'created_at'),
        ('otp_codes', 'expires_at'),
        ('otp_codes', 'created_at'),
        ('reviews', 'created_at'),
    ]

    for table, column in timezone_alters:
        try:
            conn.execute(
                sa.text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMP WITH TIME ZONE")
            )
        except Exception:
            pass


def downgrade() -> None:
    # --- Revert timezone changes (PostgreSQL) ---
    conn = op.get_bind()

    timezone_downgrades = [
        ('users', 'created_at'),
        ('users', 'updated_at'),
        ('appointments', 'appointment_date'),
        ('appointments', 'created_at'),
        ('appointments', 'updated_at'),
        ('client_profiles', 'created_at'),
        ('client_profiles', 'updated_at'),
        ('master_profiles', 'created_at'),
        ('master_profiles', 'updated_at'),
        ('services', 'created_at'),
        ('services', 'updated_at'),
        ('working_hours', 'created_at'),
        ('working_hours', 'updated_at'),
        ('audit_logs', 'created_at'),
        ('blocked_slots', 'start_dt'),
        ('blocked_slots', 'end_dt'),
        ('blocked_slots', 'created_at'),
        ('blocked_slots', 'updated_at'),
        ('refresh_tokens', 'expires_at'),
        ('refresh_tokens', 'revoked_at'),
        ('refresh_tokens', 'created_at'),
        ('otp_codes', 'expires_at'),
        ('otp_codes', 'created_at'),
        ('reviews', 'created_at'),
    ]

    for table, column in timezone_downgrades:
        try:
            conn.execute(
                sa.text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE")
            )
        except Exception:
            pass

    # --- Restore removed columns ---
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN telegram_user_id INTEGER"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_telegram_user_id ON users (telegram_user_id)"))
    except Exception:
        pass

    for col in ['cabinet_address', 'cabinet_lon', 'cabinet_lat']:
        try:
            conn.execute(sa.text(f"ALTER TABLE master_profiles ADD COLUMN {col} VARCHAR(500)"))
        except Exception:
            pass

    for col in ['preferred_location', 'location_lon', 'location_lat']:
        try:
            conn.execute(sa.text(f"ALTER TABLE client_profiles ADD COLUMN {col} VARCHAR(500)"))
        except Exception:
            pass

    # --- Restore removed tables ---
    try:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS social_accounts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider VARCHAR(50) NOT NULL,
                provider_user_id VARCHAR(255) NOT NULL,
                provider_email VARCHAR(255),
                provider_phone VARCHAR(20),
                display_name VARCHAR(100),
                avatar_url VARCHAR(500),
                access_token VARCHAR(2000),
                refresh_token VARCHAR(2000),
                token_expires_at TIMESTAMP,
                is_active BOOLEAN,
                linked_at TIMESTAMP,
                last_used_at TIMESTAMP,
                CONSTRAINT uq_social_provider_user UNIQUE (provider, provider_user_id)
            )
        """))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_social_accounts_user_id ON social_accounts (user_id)"))
        conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_social_accounts_provider ON social_accounts (provider)"))
    except Exception:
        pass

    try:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS locations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                city_id INTEGER REFERENCES cities(id) ON DELETE SET NULL,
                value VARCHAR(500),
                unrestricted_value VARCHAR(500),
                lat FLOAT,
                lon FLOAT,
                street VARCHAR(300),
                building VARCHAR(50),
                apartment VARCHAR(50),
                location_type VARCHAR(20),
                is_active BOOLEAN,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                CONSTRAINT uq_user_location UNIQUE (user_id)
            )
        """))
    except Exception:
        pass
