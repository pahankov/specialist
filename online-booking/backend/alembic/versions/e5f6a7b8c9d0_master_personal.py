"""Master personal data: surname, cabinet address, certificates.

- `users.last_name` NULLABLE (existing rows keep full `name` as-is).
- `master_profiles.cabinet_address` NULLABLE free text (DaData-picked).
- `master_profiles.certificates` JSON list [{name, url?}].
Idempotent (IF NOT EXISTS / inspect guards).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: str = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100)'
        ))
        bind.execute(sa.text(
            'ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS '
            'cabinet_address VARCHAR(500)'
        ))
        bind.execute(sa.text(
            'ALTER TABLE master_profiles ADD COLUMN IF NOT EXISTS '
            "certificates JSON NOT NULL DEFAULT '[]'"
        ))
    else:
        with op.batch_alter_table('users') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('users')]
            if 'last_name' not in cols:
                batch_op.add_column(sa.Column('last_name', sa.String(100), nullable=True))
        with op.batch_alter_table('master_profiles') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('master_profiles')]
            if 'cabinet_address' not in cols:
                batch_op.add_column(sa.Column('cabinet_address', sa.String(500), nullable=True))
            if 'certificates' not in cols:
                batch_op.add_column(sa.Column('certificates', sa.JSON(),
                                              nullable=False, default=list))


def downgrade() -> None:
    with op.batch_alter_table('master_profiles') as batch_op:
        batch_op.drop_column('certificates')
        batch_op.drop_column('cabinet_address')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('last_name')
