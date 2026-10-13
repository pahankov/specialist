"""Blacklist flag on master_hidden_clients (block new bookings). Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f101a2b3c4d'
down_revision: str = '0e0f1a2b3c4d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE master_hidden_clients '
            'ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE'))
        bind.execute(sa.text(
            'ALTER TABLE master_hidden_clients '
            'ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMPTZ'))
    else:
        with op.batch_alter_table('master_hidden_clients') as batch_op:
            cols = [c['name'] for c in
                    sa.inspect(bind).get_columns('master_hidden_clients')]
            if 'is_blocked' not in cols:
                batch_op.add_column(
                    sa.Column('is_blocked', sa.Boolean(), nullable=False,
                              server_default=sa.false()))
            if 'blocked_at' not in cols:
                batch_op.add_column(
                    sa.Column('blocked_at', sa.DateTime(timezone=True),
                              nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('master_hidden_clients') as batch_op:
        batch_op.drop_column('blocked_at')
        batch_op.drop_column('is_blocked')
