"""Personal coupons (master -> own clients)."""
revision = "16a1b2c3d4e5"
down_revision = "15a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("master_id", sa.Integer(), nullable=False, index=True),
        sa.Column("code", sa.String(24), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False, server_default="percent"),
        sa.Column("value", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("user_ids", sa.JSON(), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["master_id"], ["master_profiles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_coupons_master_code", "coupons", ["master_id", "code"], unique=True)
    op.create_table(
        "coupon_uses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("coupon_id", sa.Integer(), nullable=False, index=True),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["coupon_id"], ["coupons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )


def downgrade():
    from alembic import op

    op.drop_table("coupon_uses")
    op.drop_index("ix_coupons_master_code", table_name="coupons")
    op.drop_table("coupons")
