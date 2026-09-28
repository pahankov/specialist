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


def upgrade() -> None:
    # --- Clean up removed tables/columns ---
    op.drop_table('locations')
    with op.batch_alter_table('social_accounts', schema=None) as batch_op:
        batch_op.drop_index('ix_social_accounts_provider')
        batch_op.drop_index('ix_social_accounts_user_id')
    op.drop_table('social_accounts')

    with op.batch_alter_table('client_profiles', schema=None) as batch_op:
        batch_op.drop_column('location_lat')
        batch_op.drop_column('location_lon')
        batch_op.drop_column('preferred_location')

    with op.batch_alter_table('master_profiles', schema=None) as batch_op:
        batch_op.drop_column('cabinet_lat')
        batch_op.drop_column('cabinet_lon')
        batch_op.drop_column('cabinet_address')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_telegram_user_id')
        batch_op.drop_column('telegram_user_id')

    # --- Fix timezone in DateTime columns (PostgreSQL) ---
    # These explicit type changes ensure all DateTime columns use TIMESTAMP WITH TIME ZONE
    conn = op.get_bind()
    dialect_name = getattr(conn, 'dialect', None)
    if dialect_name is not None and dialect_name.name == 'postgresql':
        # users table
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # appointments table
        with op.batch_alter_table('appointments', schema=None) as batch_op:
            batch_op.alter_column('appointment_date',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=False)
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # client_profiles table
        with op.batch_alter_table('client_profiles', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # master_profiles table
        with op.batch_alter_table('master_profiles', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # services table
        with op.batch_alter_table('services', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # working_hours table
        with op.batch_alter_table('working_hours', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # audit_logs table
        with op.batch_alter_table('audit_logs', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # blocked_slots table
        with op.batch_alter_table('blocked_slots', schema=None) as batch_op:
            batch_op.alter_column('start_dt',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=False)
            batch_op.alter_column('end_dt',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=False)
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # refresh_tokens table
        with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
            batch_op.alter_column('expires_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=False)
            batch_op.alter_column('revoked_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # otp_codes table
        with op.batch_alter_table('otp_codes', schema=None) as batch_op:
            batch_op.alter_column('expires_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=False)
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)

        # reviews table
        with op.batch_alter_table('reviews', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DATETIME(),
                                type_=sa.DateTime(timezone=True),
                                existing_nullable=True)


def downgrade() -> None:
    # --- Revert timezone changes (PostgreSQL) ---
    conn = op.get_bind()
    dialect_name = getattr(conn, 'dialect', None)
    if dialect_name is not None and dialect_name.name == 'postgresql':
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('appointments', schema=None) as batch_op:
            batch_op.alter_column('appointment_date',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=False)
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('client_profiles', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('master_profiles', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('services', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('working_hours', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('audit_logs', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('blocked_slots', schema=None) as batch_op:
            batch_op.alter_column('start_dt',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=False)
            batch_op.alter_column('end_dt',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=False)
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('updated_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
            batch_op.alter_column('expires_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=False)
            batch_op.alter_column('revoked_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('otp_codes', schema=None) as batch_op:
            batch_op.alter_column('expires_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=False)
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

        with op.batch_alter_table('reviews', schema=None) as batch_op:
            batch_op.alter_column('created_at',
                                existing_type=sa.DateTime(timezone=True),
                                type_=sa.DATETIME(),
                                existing_nullable=True)

    # --- Restore removed tables/columns ---
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telegram_user_id', sa.INTEGER(), nullable=True))
        batch_op.create_index('ix_users_telegram_user_id', ['telegram_user_id'], unique=False)

    with op.batch_alter_table('master_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cabinet_address', sa.VARCHAR(length=500), nullable=True))
        batch_op.add_column(sa.Column('cabinet_lon', sa.FLOAT(), nullable=True))
        batch_op.add_column(sa.Column('cabinet_lat', sa.FLOAT(), nullable=True))

    with op.batch_alter_table('client_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preferred_location', sa.VARCHAR(length=500), nullable=True))
        batch_op.add_column(sa.Column('location_lon', sa.FLOAT(), nullable=True))
        batch_op.add_column(sa.Column('location_lat', sa.FLOAT(), nullable=True))

    op.create_table('social_accounts',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('user_id', sa.INTEGER(), nullable=False),
        sa.Column('provider', sa.VARCHAR(length=50), nullable=False),
        sa.Column('provider_user_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('provider_email', sa.VARCHAR(length=255), nullable=True),
        sa.Column('provider_phone', sa.VARCHAR(length=20), nullable=True),
        sa.Column('display_name', sa.VARCHAR(length=100), nullable=True),
        sa.Column('avatar_url', sa.VARCHAR(length=500), nullable=True),
        sa.Column('access_token', sa.VARCHAR(length=2000), nullable=True),
        sa.Column('refresh_token', sa.VARCHAR(length=2000), nullable=True),
        sa.Column('token_expires_at', sa.DATETIME(), nullable=True),
        sa.Column('is_primary', sa.BOOLEAN(), nullable=True),
        sa.Column('linked_at', sa.DATETIME(), nullable=True),
        sa.Column('last_used_at', sa.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_social_provider_user')
    )
    with op.batch_alter_table('social_accounts', schema=None) as batch_op:
        batch_op.create_index('ix_social_accounts_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_social_accounts_provider', ['provider'], unique=False)

    op.create_table('locations',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('user_id', sa.INTEGER(), nullable=True),
        sa.Column('city_id', sa.INTEGER(), nullable=True),
        sa.Column('value', sa.VARCHAR(length=500), nullable=True),
        sa.Column('unrestricted_value', sa.VARCHAR(length=500), nullable=True),
        sa.Column('lat', sa.FLOAT(), nullable=True),
        sa.Column('lon', sa.FLOAT(), nullable=True),
        sa.Column('street', sa.VARCHAR(length=300), nullable=True),
        sa.Column('building', sa.VARCHAR(length=50), nullable=True),
        sa.Column('apartment', sa.VARCHAR(length=50), nullable=True),
        sa.Column('location_type', sa.VARCHAR(length=20), nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), nullable=True),
        sa.Column('created_at', sa.DATETIME(), nullable=True),
        sa.Column('updated_at', sa.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
