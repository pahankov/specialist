"""Service.category for client-side grouping + backfill by name keywords.

New column is NULLABLE (no default pressure on existing rows); the backfill
assigns categories by Russian name stems, leftovers become 'Прочее'.
Idempotent (IF NOT EXISTS on PG).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c1d2e3'
down_revision: str = 'e6f7a8b9c1d2'
branch_labels = None
depends_on = None

# (category, LIKE stems) — first match wins.
CATEGORY_RULES = [
    ("Ногти", ["%ногт%", "%маник%", "%педик%"]),
    ("Шугаринг", ["%шугаринг%", "%депил%", "%воск%", "%эпиляц%"]),
    ("Ресницы и брови", ["%ресниц%", "%бров%", "%lash%", "%brow%"]),
    ("Волосы", ["%волос%", "%стриж%", "%окраш%", "%уклад%", "%прическ%"]),
    ("Массаж", ["%массаж%"]),
    ("Макияж", ["%макияж%", "%мейк%", "%визаж%"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE services ADD COLUMN IF NOT EXISTS category VARCHAR(50)'
        ))
    else:
        with op.batch_alter_table('services') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('services')]
            if 'category' not in cols:
                batch_op.add_column(sa.Column('category', sa.String(50), nullable=True))

    for category, stems in CATEGORY_RULES:
        cond = " OR ".join(f"LOWER(name) LIKE '{s}'" for s in stems)
        bind.execute(sa.text(
            f"UPDATE services SET category = '{category}' "
            f"WHERE category IS NULL AND ({cond})"
        ))
    bind.execute(sa.text(
        "UPDATE services SET category = 'Прочее' WHERE category IS NULL"
    ))

    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_services_category '
            'ON services (category)'
        ))
    else:
        op.create_index('ix_services_category', 'services', ['category'],
                        unique=False)


def downgrade() -> None:
    op.drop_index('ix_services_category', table_name='services')
    with op.batch_alter_table('services') as batch_op:
        batch_op.drop_column('category')
