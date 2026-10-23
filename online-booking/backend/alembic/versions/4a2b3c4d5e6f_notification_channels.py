"""Notification channels, reminders and master digest.

Adds per-user delivery preferences, appointment reminder markers, external
delivery bookkeeping on the bell rows and the last login provider used by
the "auto" channel choice. Idempotent on PostgreSQL; batch mode on SQLite.
"""
from alembic import op
import sqlalchemy as sa


revision: str = '4a2b3c4d5e6f'
down_revision: str = '39e4f5a6b7c8'
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        coltype = column.type.compile(dialect=bind.dialect)
        default = ''
        if column.server_default is not None:
            arg = column.server_default.arg
            if isinstance(arg, str):
                arg = "'" + arg.replace("'", "''") + "'"
            default = f' DEFAULT {arg}'
        nullable = ' NOT NULL' if not column.nullable else ' NULL'
        bind.execute(sa.text(
            f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS '
            f'{column.name} {coltype}{nullable}{default}'
        ))
    else:
        with op.batch_alter_table(table) as batch_op:
            cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
            if column.name not in cols:
                batch_op.add_column(column)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if 'notification_preferences' not in tables:
        op.create_table(
            'notification_preferences',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column(
                'user_id', sa.Integer(),
                sa.ForeignKey('users.id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('instant_enabled', sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column('reminders_enabled', sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column('max_enabled', sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column('vk_enabled', sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column('email_enabled', sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column('preferred_channel', sa.String(16), nullable=False,
                      server_default='auto'),
            sa.Column('master_digest_enabled', sa.Boolean(), nullable=False,
                      server_default=sa.true()),
            sa.Column('digest_lead_minutes', sa.Integer(), nullable=False,
                      server_default='60'),
            sa.Column('last_digest_on', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            'ix_notification_preferences_user_id',
            'notification_preferences', ['user_id'], unique=True,
        )

    _add_column_if_missing(
        'appointments',
        sa.Column('reminder_24h_sent_at', sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        'appointments',
        sa.Column('reminder_2h_sent_at', sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        'notifications',
        sa.Column('external_sent_at', sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        'notifications',
        sa.Column('external_channel', sa.String(16), nullable=True),
    )
    _add_column_if_missing(
        'notifications',
        sa.Column('external_error', sa.String(255), nullable=True),
    )
    _add_column_if_missing(
        'users',
        sa.Column('last_login_provider', sa.String(16), nullable=True),
    )

    bind.execute(sa.text(
        'CREATE INDEX IF NOT EXISTS ix_notifications_external_sent_at '
        'ON notifications (external_sent_at)'
    ))
    if 'notification_preferences' in tables:
        bind.execute(sa.text(
            'CREATE UNIQUE INDEX IF NOT EXISTS '
            'ix_notification_preferences_user_id '
            'ON notification_preferences (user_id)'
        ))
    bind.execute(sa.text(
        "UPDATE notifications SET external_sent_at = CURRENT_TIMESTAMP, "
        "external_channel = 'backfill' WHERE external_sent_at IS NULL"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'DROP INDEX IF EXISTS ix_notifications_external_sent_at'
        ))
        for table, column in (
            ('users', 'last_login_provider'),
            ('notifications', 'external_error'),
            ('notifications', 'external_channel'),
            ('notifications', 'external_sent_at'),
            ('appointments', 'reminder_2h_sent_at'),
            ('appointments', 'reminder_24h_sent_at'),
        ):
            bind.execute(sa.text(
                f'ALTER TABLE {table} DROP COLUMN IF EXISTS {column}'
            ))
        bind.execute(sa.text(
            'DROP TABLE IF EXISTS notification_preferences'
        ))
    else:
        for table, column in (
            ('users', 'last_login_provider'),
            ('notifications', 'external_error'),
            ('notifications', 'external_channel'),
            ('notifications', 'external_sent_at'),
            ('appointments', 'reminder_2h_sent_at'),
            ('appointments', 'reminder_24h_sent_at'),
        ):
            with op.batch_alter_table(table) as batch_op:
                cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
                if column in cols:
                    batch_op.drop_column(column)
        if 'notification_preferences' in set(
            sa.inspect(bind).get_table_names()
        ):
            op.drop_table('notification_preferences')
