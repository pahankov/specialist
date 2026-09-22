"""Add otp_codes table

Revision ID: 0009_add_otp_codes
Revises: 0008_drop_old_tables
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_add_otp_codes'
down_revision: Union[str, None] = '0008_drop_old_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'otp_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('code_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_otp_codes_phone', 'otp_codes', ['phone'])
    op.create_index('ix_otp_codes_code_hash', 'otp_codes', ['code_hash'])


def downgrade() -> None:
    op.drop_index('ix_otp_codes_code_hash', table_name='otp_codes')
    op.drop_index('ix_otp_codes_phone', table_name='otp_codes')
    op.drop_table('otp_codes')
