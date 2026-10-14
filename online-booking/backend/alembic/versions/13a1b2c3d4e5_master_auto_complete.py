"""Auto-complete past bookings for masters that opted in.

MasterProfile.auto_complete (switch in panel headers, next to auto-confirm).
Nullable for old rows; lifespan backfills NULL -> False on SQLite.
"""
revision = "13a1b2c3d4e5"
down_revision = "12a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("master_profiles",
                  sa.Column("auto_complete", sa.Boolean(), nullable=True))
    try:
        op.execute("UPDATE master_profiles SET auto_complete = false "
                   "WHERE auto_complete IS NULL")
    except Exception:
        pass


def downgrade():
    from alembic import op

    op.drop_column("master_profiles", "auto_complete")
