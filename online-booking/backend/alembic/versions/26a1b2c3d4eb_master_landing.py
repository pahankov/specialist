"""Master landing preference: log in straight to the master panel. Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26a1b2c3d4eb'
down_revision: str = '25a1b2c3d4ea'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE master_profiles '
            'ADD COLUMN IF NOT EXISTS prefer_master_cabinet BOOLEAN '
            'NOT NULL DEFAULT TRUE'))
    else:
        with op.batch_alter_table('master_profiles') as batch_op:
            cols = [c['name'] for c in
                    sa.inspect(bind).get_columns('master_profiles')]
            if 'prefer_master_cabinet' not in cols:
                batch_op.add_column(
                    sa.Column('prefer_master_cabinet', sa.Boolean(),
                              nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table('master_profiles') as batch_op:
        batch_op.drop_column('prefer_master_cabinet')
