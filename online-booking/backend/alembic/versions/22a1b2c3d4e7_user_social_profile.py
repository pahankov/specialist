"""Social profile sync: users.avatar_url + users.name_source.

- avatar_url: a URL on the social provider's CDN (VK avatar / Yandex
  default_avatar_id), filled and refreshed by social logins so the client
  cabinet can show the photo. Masters keep using master_profiles.avatar_url
  (uploaded photo / preset) — this is the CLIENT-facing photo.
- name_source: where the display `name` came from (NULL / "user" / a social
  provider id). Lets social logins refresh a name they themselves set while
  never overwriting a name a human entered.
"""
revision = "22a1b2c3d4e7"
down_revision = "21a1b2c3d4e6"


def upgrade():
    from alembic import op
    import sqlalchemy as sa

    op.add_column("users",
                  sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column("users",
                  sa.Column("name_source", sa.String(16), nullable=True))


def downgrade():
    from alembic import op

    op.drop_column("users", "name_source")
    op.drop_column("users", "avatar_url")
