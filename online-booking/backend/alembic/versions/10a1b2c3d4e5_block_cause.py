"""Block cause + free-text note on master_hidden_clients. Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10a1b2c3d4e5'
down_revision: str = '0f1a2b3c4d5e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE master_hidden_clients '
            'ADD COLUMN IF NOT EXISTS block_reason VARCHAR(30)'))
        bind.execute(sa.text(
            'ALTER TABLE master_hidden_clients '
            'ADD COLUMN IF NOT EXISTS block_note VARCHAR(500)'))
    else:
        with op.batch_alter_table('master_hidden_clients') as batch_op:
            cols = [c['name'] for c in
                    sa.inspect(bind).get_columns('master_hidden_clients')]
            if 'block_reason' not in cols:
                batch_op.add_column(
                    sa.Column('block_reason', sa.String(30), nullable=True))
            if 'block_note' not in cols:
                batch_op.add_column(
                    sa.Column('block_note', sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('master_hidden_clients') as batch_op:
        batch_op.drop_column('block_note')
        batch_op.drop_column('block_reason')
