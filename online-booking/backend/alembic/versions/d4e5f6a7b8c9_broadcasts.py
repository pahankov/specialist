"""Sent-broadcast history table (what/when/to-whom per send).

One row per broadcast with a recipient snapshot — answers "какие, когда
и кому я отправлял" without regrouping inbox rows. Idempotent.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: str = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'CREATE TABLE IF NOT EXISTS notification_broadcasts ('
            'id SERIAL PRIMARY KEY, '
            'sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL, '
            'audience VARCHAR(20) NOT NULL, '
            'text TEXT NOT NULL, '
            'recipients JSON NOT NULL DEFAULT \'[]\', '
            'created_at TIMESTAMPTZ)'
        ))
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_broadcasts_sender_created '
            'ON notification_broadcasts (sender_id, created_at)'
        ))
    else:
        tables = sa.inspect(bind).get_table_names()
        if 'notification_broadcasts' not in tables:
            op.create_table(
                'notification_broadcasts',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('sender_id', sa.Integer(),
                          sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
                sa.Column('audience', sa.String(20), nullable=False),
                sa.Column('text', sa.Text(), nullable=False),
                sa.Column('recipients', sa.JSON(), nullable=False, default=list),
                sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            )
            op.create_index('ix_broadcasts_sender_created', 'notification_broadcasts',
                            ['sender_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_broadcasts_sender_created', table_name='notification_broadcasts')
    op.drop_table('notification_broadcasts')
