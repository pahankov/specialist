"""Preset avatar id (`master_profiles.avatar_preset`, NULLABLE). Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08c9d0e1f2a3'
down_revision: str = '07b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS avatar_preset VARCHAR(12)'
        ))
    else:
        with op.batch_alter_table('master_profiles') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('master_profiles')]
            if 'avatar_preset' not in cols:
                batch_op.add_column(sa.Column('avatar_preset', sa.String(12), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('master_profiles') as batch_op:
        batch_op.drop_column('avatar_preset')
