"""Half-year prepayment and explicit master-terms consent (1.88.0).

Adds the prepayment length to ledger balances (for the plan badge: 6 months
= Профи, 12 months = Бизнес) and stores the separate master-terms acceptance
stamped at activation. Idempotent on PostgreSQL; batch mode on SQLite.
"""
from alembic import op
import sqlalchemy as sa


revision: str = '39e4f5a6b7c8'
down_revision: str = '28d3e4f5a6b7'
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
        'billing_credits',
        sa.Column('prepay_months', sa.Integer(), nullable=True),
    )
    # Before 1.88.0 the only prepayment options were 1 and 12 months; every
    # existing prepayment balance was therefore annual. Backfill so old
    # balances keep the Business plan after the upgrade.
    op.get_bind().execute(sa.text(
        "UPDATE billing_credits SET prepay_months = 12 "
        "WHERE source = 'prepayment' AND prepay_months IS NULL"
    ))
    _add_column_if_missing(
        'users',
        sa.Column('master_terms_accepted_at',
                  sa.DateTime(timezone=True), nullable=True),
    )
    _add_column_if_missing(
        'users',
        sa.Column('master_terms_version', sa.String(20), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    columns = (
        ('users', 'master_terms_version'),
        ('users', 'master_terms_accepted_at'),
        ('billing_credits', 'prepay_months'),
    )
    if bind.dialect.name == 'postgresql':
        for table, column in columns:
            bind.execute(sa.text(
                f'ALTER TABLE {table} DROP COLUMN IF EXISTS {column}'
            ))
    else:
        for table, column in columns:
            with op.batch_alter_table(table) as batch_op:
                cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
                if column in cols:
                    batch_op.drop_column(column)
