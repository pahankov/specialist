"""Master auto-confirm flag for client-initiated bookings. Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11a1b2c3d4e5'
down_revision: str = '10a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE master_profiles '
            'ADD COLUMN IF NOT EXISTS auto_confirm BOOLEAN DEFAULT FALSE'))
    else:
        with op.batch_alter_table('master_profiles') as batch_op:
            cols = [c['name'] for c in
                    sa.inspect(bind).get_columns('master_profiles')]
            if 'auto_confirm' not in cols:
                batch_op.add_column(
                    sa.Column('auto_confirm', sa.Boolean(), nullable=False,
                              server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('master_profiles') as batch_op:
        batch_op.drop_column('auto_confirm')
