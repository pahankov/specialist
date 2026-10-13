"""Soft-delete marker on users (self-service account deletion, retention 3y). Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d0e1f2a3b4c'
down_revision: str = '0cf0a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ'))
    else:
        with op.batch_alter_table('users') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('users')]
            if 'deleted_at' not in cols:
                batch_op.add_column(
                    sa.Column('deleted_at', sa.DateTime(timezone=True),
                              nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('deleted_at')
