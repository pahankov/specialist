"""Per-master client hiding (remove from my lists, keep history). Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e0f1a2b3c4d'
down_revision: str = '0d0e1f2a3b4c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'CREATE TABLE IF NOT EXISTS master_hidden_clients ('
            'id SERIAL PRIMARY KEY, '
            'master_profile_id INTEGER NOT NULL REFERENCES master_profiles(id) ON DELETE CASCADE, '
            'client_profile_id INTEGER NOT NULL REFERENCES client_profiles(id) ON DELETE CASCADE, '
            'hidden_at TIMESTAMPTZ DEFAULT now(), '
            'UNIQUE (master_profile_id, client_profile_id))'))
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_hidden_by_master '
            'ON master_hidden_clients (master_profile_id)'))
    else:
        op.create_table(
            'master_hidden_clients',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('master_profile_id', sa.Integer(),
                      sa.ForeignKey('master_profiles.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('client_profile_id', sa.Integer(),
                      sa.ForeignKey('client_profiles.id', ondelete='CASCADE'),
                      nullable=False),
            sa.Column('hidden_at', sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint('master_profile_id', 'client_profile_id'),
            sa.Index('ix_hidden_by_master', 'master_profile_id'),
        )


def downgrade() -> None:
    op.drop_table('master_hidden_clients')
