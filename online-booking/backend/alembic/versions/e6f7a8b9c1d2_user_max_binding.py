"""User.max_user_id: bound MAX account for push-code login.

After the first MAX login the sender id is stored on the user, so later
/max/start calls push the code straight into the known dialog.
/start falls back to the share-number flow when unbound. Idempotent.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c1d2'
down_revision: str = 'd5e6f7a8b9c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS '
            'max_user_id BIGINT'
        ))
        bind.execute(sa.text(
            'CREATE UNIQUE INDEX IF NOT EXISTS ix_users_max_user_id '
            'ON users (max_user_id)'
        ))
    else:
        with op.batch_alter_table('users') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('users')]
            if 'max_user_id' not in cols:
                batch_op.add_column(sa.Column('max_user_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_users_max_user_id', 'users', ['max_user_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_max_user_id', table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('max_user_id')
