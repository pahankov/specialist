"""Archive reason on master_hidden_clients. Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f1a2b3c4d5e'
down_revision: str = '0f101a2b3c4d'
branch_labels = None
depends_on = None

HIDE_REASONS = ('moved', 'left', 'inactive', 'deceased', 'other')


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE master_hidden_clients '
            'ADD COLUMN IF NOT EXISTS hidden_reason VARCHAR(30)'))
    else:
        with op.batch_alter_table('master_hidden_clients') as batch_op:
            cols = [c['name'] for c in
                    sa.inspect(bind).get_columns('master_hidden_clients')]
            if 'hidden_reason' not in cols:
                batch_op.add_column(
                    sa.Column('hidden_reason', sa.String(30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('master_hidden_clients') as batch_op:
        batch_op.drop_column('hidden_reason')
