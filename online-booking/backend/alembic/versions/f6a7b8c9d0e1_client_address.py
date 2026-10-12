"""Client location address (matching key stays users.city_id).

`client_profiles.address` NULLABLE free text (DaData-picked). Idempotent.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: str = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE client_profiles ADD COLUMN IF NOT EXISTS address VARCHAR(500)'
        ))
    else:
        with op.batch_alter_table('client_profiles') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('client_profiles')]
            if 'address' not in cols:
                batch_op.add_column(sa.Column('address', sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('client_profiles') as batch_op:
        batch_op.drop_column('address')
