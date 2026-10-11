"""Track which master created a user (own-clients scope).

`users.created_by` is NULLABLE (existing rows stay NULL = visible to
superadmin only via global lists; masters resolve own clients through
appointments). Idempotent (IF NOT EXISTS on PG).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: str = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by INTEGER '
            'REFERENCES users(id) ON DELETE SET NULL'
        ))
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_users_created_by ON users (created_by)'
        ))
    else:
        with op.batch_alter_table('users') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('users')]
            if 'created_by' not in cols:
                batch_op.add_column(
                    sa.Column('created_by', sa.Integer(),
                              sa.ForeignKey('users.id', ondelete='SET NULL'),
                              nullable=True))
        op.create_index('ix_users_created_by', 'users', ['created_by'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_users_created_by', table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('created_by')
