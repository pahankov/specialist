"""MAX profile extras: username + contact vCard email.

users.max_username — public MAX nickname captured at binding time.
otp_codes.max_username/max_user_email — carried from the dialog (webhook)
to /max/verify, where the account is created/backfilled.
"""
revision = "19a1b2c3d4e5"
down_revision = "18a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("users",
                  sa.Column("max_username", sa.String(64), nullable=True))
    op.add_column("otp_codes",
                  sa.Column("max_username", sa.String(64), nullable=True))
    op.add_column("otp_codes",
                  sa.Column("max_user_email", sa.String(255), nullable=True))


def downgrade():
    from alembic import op

    op.drop_column("otp_codes", "max_user_email")
    op.drop_column("otp_codes", "max_username")
    op.drop_column("users", "max_username")
