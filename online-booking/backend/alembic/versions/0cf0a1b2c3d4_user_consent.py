"""Legal consent proof on users (152-FZ + offer versions). Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0cf0a1b2c3d4'
down_revision: str = '0af0e1d2c3b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for col, ddl in (
            ('consent_at',
             'ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_at TIMESTAMPTZ'),
            ('consent_policy_version',
             'ALTER TABLE users ADD COLUMN IF NOT EXISTS '
             'consent_policy_version VARCHAR(20)'),
            ('consent_offer_version',
             'ALTER TABLE users ADD COLUMN IF NOT EXISTS '
             'consent_offer_version VARCHAR(20)'),
        ):
            bind.execute(sa.text(ddl))
    else:
        with op.batch_alter_table('users') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('users')]
            if 'consent_at' not in cols:
                batch_op.add_column(
                    sa.Column('consent_at', sa.DateTime(timezone=True),
                              nullable=True))
            if 'consent_policy_version' not in cols:
                batch_op.add_column(
                    sa.Column('consent_policy_version', sa.String(20),
                              nullable=True))
            if 'consent_offer_version' not in cols:
                batch_op.add_column(
                    sa.Column('consent_offer_version', sa.String(20),
                              nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('consent_offer_version')
        batch_op.drop_column('consent_policy_version')
        batch_op.drop_column('consent_at')
