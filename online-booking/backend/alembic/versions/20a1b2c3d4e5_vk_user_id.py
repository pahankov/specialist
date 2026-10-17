"""VK ID binding: users.vk_user_id (login match key, like max_user_id).

After the first VK ID login the VK user id is stored on the account, so
subsequent logins match directly (no phone/email needed). NULLs are
distinct in PG/SQLite unique indexes, so unbound users never collide.
"""
revision = "20a1b2c3d4e5"
down_revision = "19a1b2c3d4e5"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("users",
                  sa.Column("vk_user_id", sa.BigInteger(), nullable=True))
    op.create_index(
        "ix_users_vk_user_id", "users", ["vk_user_id"], unique=True)


def downgrade():
    from alembic import op

    op.drop_index("ix_users_vk_user_id", table_name="users")
    op.drop_column("users", "vk_user_id")
