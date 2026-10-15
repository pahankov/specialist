"""Fixed RUB discounts alongside percentage ones (stack: % first, then -RUB)."""
revision = "17a1b2c3d4e5"
down_revision = "16a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("services",
                  sa.Column("discount_fixed", sa.Numeric(10, 2),
                            nullable=True, server_default="0"))
    op.add_column("service_bundles",
                  sa.Column("discount_fixed", sa.Numeric(10, 2),
                            nullable=True, server_default="0"))


def downgrade():
    from alembic import op

    op.drop_column("service_bundles", "discount_fixed")
    op.drop_column("services", "discount_fixed")
