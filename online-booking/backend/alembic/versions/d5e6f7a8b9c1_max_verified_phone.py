"""MAX verified-phone flag on otp_codes.

True when the dialog number came from a request_contact share whose HMAC
matched (proven MAX-bound number) — such users are created verified.
Typed text numbers stay unverified. Idempotent (IF NOT EXISTS on PG).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c1'
down_revision: str = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'ALTER TABLE otp_codes ADD COLUMN IF NOT EXISTS '
            'max_verified_phone BOOLEAN NOT NULL DEFAULT FALSE'
        ))
    else:
        with op.batch_alter_table('otp_codes') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('otp_codes')]
            if 'max_verified_phone' not in cols:
                batch_op.add_column(
                    sa.Column('max_verified_phone', sa.Boolean(),
                              nullable=False, server_default='0')
                )


def downgrade() -> None:
    with op.batch_alter_table('otp_codes') as batch_op:
        batch_op.drop_column('max_verified_phone')
