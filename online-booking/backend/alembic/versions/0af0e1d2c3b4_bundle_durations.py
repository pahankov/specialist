"""Per-service duration overrides inside bundles. Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0af0e1d2c3b4'
down_revision: str = '09e0f1a2b3c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE service_bundles ADD COLUMN IF NOT EXISTS durations JSON'
        ))
    else:
        with op.batch_alter_table('service_bundles') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('service_bundles')]
            if 'durations' not in cols:
                batch_op.add_column(sa.Column('durations', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('service_bundles') as batch_op:
        batch_op.drop_column('durations')
