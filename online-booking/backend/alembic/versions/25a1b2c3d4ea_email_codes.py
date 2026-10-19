"""email_codes: six-digit codes sent to addresses (1.79.0).

Backs the password reset («Забыли пароль») and, later in this release,
email confirmation in the cabinet. Codes are single-use, expire by TTL
and burn after several wrong attempts — see app.services.email_codes.

Idempotent: CREATE ... IF NOT EXISTS (PG) / inspector check (SQLite).

Revision ID: 25a1b2c3d4ea
Revises: 24a1b2c3d4e9
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25a1b2c3d4ea'
down_revision: str = '24a1b2c3d4e9'
branch_labels = None
depends_on = None


def _create_table(bind) -> None:
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(
            "CREATE TABLE IF NOT EXISTS email_codes ("
            "id SERIAL PRIMARY KEY, "
            "email VARCHAR(255) NOT NULL, "
            "purpose VARCHAR(20) NOT NULL, "
            "code_hash VARCHAR(64) NOT NULL, "
            "expires_at TIMESTAMPTZ NOT NULL, "
            "is_used BOOLEAN NOT NULL DEFAULT FALSE, "
            "attempts INTEGER NOT NULL DEFAULT 0, "
            "created_at TIMESTAMPTZ)"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_email_codes_email "
            "ON email_codes (email)"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_email_codes_email_purpose "
            "ON email_codes (email, purpose)"
        ))
    else:
        if "email_codes" not in sa.inspect(bind).get_table_names():
            op.create_table(
                "email_codes",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("email", sa.String(255), nullable=False),
                sa.Column("purpose", sa.String(20), nullable=False),
                sa.Column("code_hash", sa.String(64), nullable=False),
                sa.Column("expires_at", sa.DateTime(timezone=True),
                          nullable=False),
                sa.Column("is_used", sa.Boolean(), nullable=False,
                          server_default=sa.text("0")),
                sa.Column("attempts", sa.Integer(), nullable=False,
                          server_default=sa.text("0")),
                sa.Column("created_at", sa.DateTime(timezone=True),
                          nullable=True),
            )
            op.create_index("ix_email_codes_email", "email_codes",
                            ["email"], unique=False)
            op.create_index("ix_email_codes_email_purpose", "email_codes",
                            ["email", "purpose"], unique=False)


def upgrade() -> None:
    _create_table(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("DROP TABLE IF EXISTS email_codes"))
    else:
        if "email_codes" in sa.inspect(bind).get_table_names():
            op.drop_table("email_codes")
