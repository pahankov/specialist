"""Snapshot discount provenance on appointments (visible in lists/slots)."""
revision = "18a1b2c3d4e5"
down_revision = "17a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("appointments",
                  sa.Column("discount_label", sa.String(200), nullable=True))


def downgrade():
    from alembic import op

    op.drop_column("appointments", "discount_label")
