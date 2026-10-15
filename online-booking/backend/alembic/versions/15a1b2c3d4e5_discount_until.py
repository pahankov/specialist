"""Time-boxed discounts: discount_until on services and bundles."""
revision = "15a1b2c3d4e5"
down_revision = "14a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("services",
                  sa.Column("discount_until", sa.DateTime(), nullable=True))
    op.add_column("service_bundles",
                  sa.Column("discount_until", sa.DateTime(), nullable=True))


def downgrade():
    from alembic import op

    op.drop_column("service_bundles", "discount_until")
    op.drop_column("services", "discount_until")
