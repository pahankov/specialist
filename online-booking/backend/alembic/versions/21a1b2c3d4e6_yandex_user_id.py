"""Yandex ID binding: users.yandex_user_id (login match key, like vk_user_id).

After the first Yandex ID login the Yandex user id is stored on the account,
so subsequent logins match directly (no phone/email needed). NULLs are
distinct in PG/SQLite unique indexes, so unbound users never collide.
"""
revision = "21a1b2c3d4e6"
down_revision = "20a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("users",
                  sa.Column("yandex_user_id", sa.BigInteger(), nullable=True))
    op.create_index(
        "ix_users_yandex_user_id", "users", ["yandex_user_id"], unique=True)


def downgrade():
    from alembic import op

    op.drop_index("ix_users_yandex_user_id", table_name="users")
    op.drop_column("users", "yandex_user_id")
