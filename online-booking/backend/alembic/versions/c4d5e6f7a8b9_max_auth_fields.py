"""MAX chat-bot auth fields on otp_codes.

Adds channel discriminator ('sms' | 'max'), the MAX sender id that confirmed
the code, and the sender display name (used as the client name fallback).
Idempotent on PostgreSQL (IF NOT EXISTS); SQLite path via batch mode.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: str = '5280b944554f'
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == 'postgresql':
        # Alembic has no native IF NOT EXISTS for ADD COLUMN — use raw DDL.
        # NOTE: string DEFAULTs must be single-quoted (PG rejects bare
        # `DEFAULT sms` with "cannot use column reference in DEFAULT").
        coltype = column.type.compile(dialect=bind.dialect)
        default = ''
        if column.server_default is not None:
            arg = column.server_default.arg
            if isinstance(arg, str):
                arg = "'" + arg.replace("'", "''") + "'"
            default = f" DEFAULT {arg}"
        nullable = '' if column.nullable else ' NOT NULL'
        bind.execute(
            sa.text(
                f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS '
                f'{column.name} {coltype}{nullable}{default}'
            )
        )
    else:
        with op.batch_alter_table(table) as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns(table)]
            if column.name not in cols:
                batch_op.add_column(column)


def upgrade() -> None:
    _add_column_if_missing(
        'otp_codes',
        sa.Column('channel', sa.String(10), nullable=False,
                  server_default='sms'),
    )
    _add_column_if_missing(
        'otp_codes',
        sa.Column('max_user_id', sa.BigInteger(), nullable=True),
    )
    _add_column_if_missing(
        'otp_codes',
        sa.Column('max_user_name', sa.String(200), nullable=True),
    )
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_otp_codes_channel '
            'ON otp_codes (channel)'
        ))
    else:
        op.create_index('ix_otp_codes_channel', 'otp_codes', ['channel'],
                        unique=False)


def downgrade() -> None:
    op.drop_index('ix_otp_codes_channel', table_name='otp_codes')
    with op.batch_alter_table('otp_codes') as batch_op:
        batch_op.drop_column('max_user_name')
        batch_op.drop_column('max_user_id')
        batch_op.drop_column('channel')
