"""Internal bell notifications table.

Creates `notifications` (one row per recipient, no messenger binding).
Idempotent IF NOT EXISTS on PG; batch mode on SQLite.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str = 'f7a8b9c1d2e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'CREATE TABLE IF NOT EXISTS notifications ('
            'id SERIAL PRIMARY KEY, '
            'sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL, '
            'recipient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, '
            'text TEXT NOT NULL, '
            'audience VARCHAR(20), '
            'is_read BOOLEAN NOT NULL DEFAULT FALSE, '
            'created_at TIMESTAMPTZ, '
            'read_at TIMESTAMPTZ)'
        ))
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_notifications_recipient_created '
            'ON notifications (recipient_id, created_at)'
        ))
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_notifications_recipient_unread '
            'ON notifications (recipient_id, is_read)'
        ))
    else:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'),
                      nullable=True),
            sa.Column('recipient_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('audience', sa.String(20), nullable=True),
            sa.Column('is_read', sa.Boolean(), nullable=False, default=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_notifications_recipient_created', 'notifications',
                        ['recipient_id', 'created_at'], unique=False)
        op.create_index('ix_notifications_recipient_unread', 'notifications',
                        ['recipient_id', 'is_read'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_notifications_recipient_unread', table_name='notifications')
    op.drop_index('ix_notifications_recipient_created', table_name='notifications')
    op.drop_table('notifications')
