"""Service bundles (complexes) + appointment bundle snapshots. Idempotent."""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09e0f1a2b3c4'
down_revision: str = '08c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text(
            'CREATE TABLE IF NOT EXISTS service_bundles ('
            'id SERIAL PRIMARY KEY, '
            'master_id INTEGER NOT NULL REFERENCES master_profiles(id) ON DELETE CASCADE, '
            'name VARCHAR(200) NOT NULL, '
            'service_ids JSON NOT NULL DEFAULT \'[]\', '
            'price NUMERIC(10, 2), '
            'is_active BOOLEAN DEFAULT TRUE, '
            'created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)'
        ))
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_service_bundles_master '
            'ON service_bundles (master_id)'
        ))
        for col, ddl in (
            ('bundle_id',
             'ALTER TABLE appointments ADD COLUMN IF NOT EXISTS bundle_id INTEGER '
             'REFERENCES service_bundles(id) ON DELETE SET NULL'),
            ('bundle_name',
             'ALTER TABLE appointments ADD COLUMN IF NOT EXISTS bundle_name VARCHAR(200)'),
            ('duration_minutes',
             'ALTER TABLE appointments ADD COLUMN IF NOT EXISTS duration_minutes INTEGER'),
            ('price',
             'ALTER TABLE appointments ADD COLUMN IF NOT EXISTS price NUMERIC(10, 2)'),
        ):
            bind.execute(sa.text(ddl))
        bind.execute(sa.text(
            'CREATE INDEX IF NOT EXISTS ix_appointments_bundle '
            'ON appointments (bundle_id)'
        ))
        # Bundle bookings carry service_id=NULL.
        bind.execute(sa.text(
            'ALTER TABLE appointments ALTER COLUMN service_id DROP NOT NULL'
        ))
    else:
        op.create_table(
            'service_bundles',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('master_id', sa.Integer(),
                      sa.ForeignKey('master_profiles.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('service_ids', sa.JSON(), nullable=False, default=list),
            sa.Column('price', sa.Numeric(10, 2), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            if_not_exists=True,
        )
        with op.batch_alter_table('appointments') as batch_op:
            cols = [c['name'] for c in sa.inspect(bind).get_columns('appointments')]
            if 'bundle_id' not in cols:
                # No inline FK: batch mode requires named constraints on
                # sqlite (FKs aren't enforced there anyway; PG keeps the
                # real one in the branch above).
                batch_op.add_column(sa.Column(
                    'bundle_id', sa.Integer(), nullable=True, index=True))
            if 'bundle_name' not in cols:
                batch_op.add_column(sa.Column('bundle_name', sa.String(200), nullable=True))
            if 'duration_minutes' not in cols:
                batch_op.add_column(sa.Column('duration_minutes', sa.Integer(), nullable=True))
            if 'price' not in cols:
                batch_op.add_column(sa.Column('price', sa.Numeric(10, 2), nullable=True))
            batch_op.alter_column('service_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('appointments') as batch_op:
        batch_op.drop_column('price')
        batch_op.drop_column('duration_minutes')
        batch_op.drop_column('bundle_name')
        batch_op.drop_column('bundle_id')
        batch_op.alter_column('service_id', existing_type=sa.Integer(), nullable=False)
    op.drop_table('service_bundles')
