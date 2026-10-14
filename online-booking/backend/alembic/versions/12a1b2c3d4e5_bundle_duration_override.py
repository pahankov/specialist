"""Manual total time override for service bundles. Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12a1b2c3d4e5'
down_revision: str = '11a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE service_bundles '
            'ADD COLUMN IF NOT EXISTS duration_override INTEGER'))
    else:
        with op.batch_alter_table('service_bundles') as batch_op:
            cols = [c['name'] for c in
                    sa.inspect(bind).get_columns('service_bundles')]
            if 'duration_override' not in cols:
                batch_op.add_column(
                    sa.Column('duration_override', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('service_bundles') as batch_op:
        batch_op.drop_column('duration_override')
