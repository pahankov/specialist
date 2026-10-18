"""Drop the legacy plaintext otp_codes.code column.

The production otp_codes table predates the baseline squash: it still
carried the pre-hash `code VARCHAR(10) NOT NULL` column (no default)
next to the mapped `code_hash`. The ORM never fills `code`, so every
INSERT violated the NOT NULL constraint - 500 on /auth/max/start and
/auth/send-otp in production only (local SQLite tables are created from
the current model via create_all and never had the column).

Idempotent: `DROP COLUMN IF EXISTS` is a no-op when the column was
already removed by hand, so a re-run of `alembic upgrade head` on a
repaired database stays green.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23a1b2c3d4e8'
down_revision: str = '22a1b2c3d4e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE otp_codes DROP COLUMN IF EXISTS code'
        ))
    else:
        cols = [c['name'] for c in sa.inspect(bind).get_columns('otp_codes')]
        if 'code' in cols:
            with op.batch_alter_table('otp_codes') as batch_op:
                batch_op.drop_column('code')


def downgrade() -> None:
    bind = op.get_bind()
    # Nullable on the way back: surviving rows never store a plaintext code.
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE otp_codes ADD COLUMN IF NOT EXISTS code VARCHAR(10)'
        ))
    else:
        cols = [c['name'] for c in sa.inspect(bind).get_columns('otp_codes')]
        if 'code' not in cols:
            with op.batch_alter_table('otp_codes') as batch_op:
                batch_op.add_column(sa.Column('code', sa.String(10),
                                              nullable=True))
