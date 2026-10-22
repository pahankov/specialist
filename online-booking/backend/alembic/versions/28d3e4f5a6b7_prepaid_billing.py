"""Prepaid billing: annual/monthly prepayment invoices and credits (1.87.0).

Prepayment invoices live outside the monthly ladder (negative period_index),
never block access, and create a long-lived ledger credit when an admin
confirms the payment. Idempotent on PostgreSQL; batch mode on SQLite.
"""
from alembic import op
import sqlalchemy as sa


revision: str = '28d3e4f5a6b7'
down_revision: str = '27b1c2d3e4f5'
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
    _add_column_if_missing(
        'master_billing_accounts',
        sa.Column('prepaid_until', sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        'billing_invoices',
        sa.Column('base_amount', sa.Numeric(10, 2), nullable=True),
    )
    _add_column_if_missing(
        'billing_invoices',
        sa.Column('kind', sa.String(24), nullable=False,
                  server_default='monthly'),
    )
    _add_column_if_missing(
        'billing_invoices',
        sa.Column('months', sa.Integer(), nullable=False,
                  server_default='1'),
    )
    bind = op.get_bind()
    indexes = {
        index['name']
        for index in sa.inspect(bind).get_indexes('billing_invoices')
    }
    if 'ix_billing_invoices_kind' not in indexes:
        op.create_index(
            'ix_billing_invoices_kind', 'billing_invoices', ['kind'])


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {
        index['name']
        for index in sa.inspect(bind).get_indexes('billing_invoices')
    }
    if 'ix_billing_invoices_kind' in indexes:
        op.drop_index('ix_billing_invoices_kind', table_name='billing_invoices')
    if bind.dialect.name == 'postgresql':
        for table, column in (
            ('billing_invoices', 'months'),
            ('billing_invoices', 'kind'),
            ('billing_invoices', 'base_amount'),
            ('master_billing_accounts', 'prepaid_until'),
        ):
            bind.execute(sa.text(
                f'ALTER TABLE {table} DROP COLUMN IF EXISTS {column}'
            ))
    else:
        for table, column in (
            ('billing_invoices', 'months'),
            ('billing_invoices', 'kind'),
            ('billing_invoices', 'base_amount'),
            ('master_billing_accounts', 'prepaid_until'),
        ):
            with op.batch_alter_table(table) as batch_op:
                cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
                if column in cols:
                    batch_op.drop_column(column)
