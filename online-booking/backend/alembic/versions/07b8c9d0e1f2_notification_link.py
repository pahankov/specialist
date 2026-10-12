"""Bell deep-link key (`notifications.link`, NULLABLE). Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07b8c9d0e1f2'
down_revision: str = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE notifications ADD COLUMN IF NOT EXISTS link VARCHAR(50)'
        ))
    else:
        with op.batch_alter_table('notifications') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('notifications')]
            if 'link' not in cols:
                batch_op.add_column(sa.Column('link', sa.String(50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('notifications') as batch_op:
        batch_op.drop_column('link')
