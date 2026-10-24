"""OTP brute-force protection: add a wrong-code counter.

Revision ID: 6c4d5e6f7081
Revises: 5b3c4d5e6f70
Create Date: 2026-10-24

The counter is burned after ``settings.SMS_MAX_ATTEMPTS`` failures. The
server default backfills existing rows and keeps raw inserts safe.
"""
from alembic import op
import sqlalchemy as sa


revision: str = "6c4d5e6f7081"
down_revision: str = "5b3c4d5e6f70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("otp_codes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("otp_codes") as batch_op:
        batch_op.drop_column("attempts")
