"""P&L categories and income/expense entries.

Creates the three accounting tables and seeds a starter chart of accounts.
Entries stay empty on purpose: the report renders zeros until real numbers
are posted. Idempotent on PostgreSQL, batch-friendly on SQLite.
"""
from alembic import op
import sqlalchemy as sa


revision: str = '5b3c4d5e6f70'
down_revision: str = '4a2b3c4d5e6f'
branch_labels = None
depends_on = None

SEED_CATEGORIES = (
    ('Услуги', 'INCOME', 'Выручка от оказанных услуг'),
    ('Товары', 'INCOME', 'Продажа товаров и косметики'),
    ('Сертификаты', 'INCOME', 'Подарочные сертификаты'),
    ('Прочие доходы', 'INCOME', 'Прочие поступления'),
    ('Аренда', 'EXPENSE', 'Аренда помещения'),
    ('Зарплаты', 'EXPENSE', 'Оплата труда мастеров и администраторов'),
    ('Материалы', 'EXPENSE', 'Расходные материалы и косметика'),
    ('Маркетинг', 'EXPENSE', 'Реклама и продвижение'),
    ('Налоги', 'EXPENSE', 'Налоги и обязательные платежи'),
    ('Прочие расходы', 'EXPENSE', 'Прочие затраты'),
)


def _create_category_table() -> None:
    op.create_table(
        'pnl_categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('name', 'kind', name='uq_pnl_category_name_kind'),
    )
    op.create_index('ix_pnl_categories_kind', 'pnl_categories', ['kind'])
    op.create_index(
        'ix_pnl_categories_kind_active', 'pnl_categories', ['kind', 'is_active'],
    )


def _create_entry_table(table: str, check_name: str) -> None:
    op.create_table(
        table,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'category_id', sa.Integer(),
            sa.ForeignKey('pnl_categories.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('occurred_on', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'created_by', sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('amount > 0', name=check_name),
    )
    op.create_index(f'ix_{table}_category_id', table, ['category_id'])
    op.create_index(f'ix_{table}_occurred_on', table, ['occurred_on'])


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if 'pnl_categories' not in tables:
        _create_category_table()
        tables.add('pnl_categories')
    if 'pnl_incomes' not in tables:
        _create_entry_table('pnl_incomes', 'ck_pnl_incomes_amount_positive')
    if 'pnl_expenses' not in tables:
        _create_entry_table('pnl_expenses', 'ck_pnl_expenses_amount_positive')

    # Seed by (name, kind) so re-running the migration never duplicates rows
    # and never overwrites an operator's edits.
    existing = {
        (row[0], row[1])
        for row in bind.execute(sa.text(
            'SELECT name, kind FROM pnl_categories'
        )).fetchall()
    }
    for name, kind, description in SEED_CATEGORIES:
        if (name, kind) in existing:
            continue
        bind.execute(
            sa.text(
                'INSERT INTO pnl_categories '
                '(name, kind, description, is_active, created_at, updated_at) '
                'VALUES (:name, :kind, :description, :is_active, '
                'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
            ),
            {
                'name': name,
                'kind': kind,
                'description': description,
                'is_active': True,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for table in ('pnl_incomes', 'pnl_expenses', 'pnl_categories'):
        if table in tables:
            op.drop_table(table)
