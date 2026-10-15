"""Percentage discounts on services and bundles (0-90, nullable = none)."""
revision = "14a1b2c3d4e5"
down_revision = "13a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("services",
                  sa.Column("discount_percent", sa.Integer(), nullable=True))
    op.add_column("service_bundles",
                  sa.Column("discount_percent", sa.Integer(), nullable=True))
    try:
        op.execute("UPDATE services SET discount_percent = 0 "
                   "WHERE discount_percent IS NULL")
        op.execute("UPDATE service_bundles SET discount_percent = 0 "
                   "WHERE discount_percent IS NULL")
    except Exception:
        pass


def downgrade():
    from alembic import op

    op.drop_column("service_bundles", "discount_percent")
    op.drop_column("services", "discount_percent")
