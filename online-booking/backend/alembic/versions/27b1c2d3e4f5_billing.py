"""Master billing: 14-day trial, invoices, credits and referrals (1.84.0).

Idempotent on PostgreSQL and batch-based on SQLite.
"""
from alembic import op
import sqlalchemy as sa


revision: str = '27b1c2d3e4f5'
down_revision: str = '26a1b2c3d4eb'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _columns(bind, table: str) -> set[str]:
    return {c['name'] for c in sa.inspect(bind).get_columns(table)}


def _add_column(bind, table: str, column: sa.Column) -> None:
    if column.name in _columns(bind, table):
        return
    op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == 'postgresql'

    if pg:
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS master_billing_accounts (
                id SERIAL PRIMARY KEY,
                master_id INTEGER NOT NULL UNIQUE
                    REFERENCES master_profiles(id) ON DELETE CASCADE,
                trial_started_at TIMESTAMPTZ NOT NULL,
                trial_ends_at TIMESTAMPTZ NOT NULL,
                billing_started_at TIMESTAMPTZ NOT NULL,
                referral_code VARCHAR(16) NOT NULL UNIQUE,
                access_status VARCHAR(20) NOT NULL DEFAULT 'trial',
                review_flag BOOLEAN NOT NULL DEFAULT FALSE,
                bonus_blocked_until TIMESTAMPTZ,
                last_processed_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_billing_accounts_status "
            "ON master_billing_accounts (access_status)"))
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS billing_invoices (
                id SERIAL PRIMARY KEY,
                master_id INTEGER NOT NULL
                    REFERENCES master_profiles(id) ON DELETE CASCADE,
                period_index INTEGER NOT NULL,
                amount NUMERIC(10,2) NOT NULL,
                credits_applied NUMERIC(10,2) NOT NULL DEFAULT 0,
                paid_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'open',
                issue_at TIMESTAMPTZ NOT NULL,
                due_at TIMESTAMPTZ NOT NULL,
                block_at TIMESTAMPTZ NOT NULL,
                period_start TIMESTAMPTZ,
                period_end TIMESTAMPTZ,
                paid_at TIMESTAMPTZ,
                payment_method VARCHAR(40),
                note TEXT,
                notified_at TIMESTAMPTZ,
                overdue_notified_at TIMESTAMPTZ,
                reminder_sent_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_billing_invoice_period
                    UNIQUE (master_id, period_index)
            )
        """))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_billing_invoices_master_status "
            "ON billing_invoices (master_id, status)"))
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS billing_credits (
                id SERIAL PRIMARY KEY,
                master_id INTEGER NOT NULL
                    REFERENCES master_profiles(id) ON DELETE CASCADE,
                source VARCHAR(30) NOT NULL,
                source_ref VARCHAR(80),
                amount NUMERIC(10,2) NOT NULL,
                remaining NUMERIC(10,2) NOT NULL,
                expires_at TIMESTAMPTZ,
                expired_at TIMESTAMPTZ,
                note TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_billing_credits_master_remaining "
            "ON billing_credits (master_id, remaining)"))
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS billing_credit_applications (
                id SERIAL PRIMARY KEY,
                credit_id INTEGER NOT NULL
                    REFERENCES billing_credits(id) ON DELETE CASCADE,
                invoice_id INTEGER NOT NULL
                    REFERENCES billing_invoices(id) ON DELETE CASCADE,
                amount NUMERIC(10,2) NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_billing_credit_invoice
                    UNIQUE (credit_id, invoice_id)
            )
        """))
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS billing_payments (
                id SERIAL PRIMARY KEY,
                invoice_id INTEGER NOT NULL
                    REFERENCES billing_invoices(id) ON DELETE CASCADE,
                amount NUMERIC(10,2) NOT NULL,
                method VARCHAR(40) NOT NULL DEFAULT 'manual',
                note TEXT,
                created_by_user_id INTEGER
                    REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS client_bonus_awards (
                id SERIAL PRIMARY KEY,
                master_id INTEGER NOT NULL UNIQUE
                    REFERENCES master_profiles(id) ON DELETE CASCADE,
                trial_started_at TIMESTAMPTZ NOT NULL,
                trial_ends_at TIMESTAMPTZ NOT NULL,
                eligible_count INTEGER NOT NULL DEFAULT 0,
                max_count INTEGER NOT NULL DEFAULT 10,
                amount NUMERIC(10,2) NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                total_candidates INTEGER NOT NULL DEFAULT 0,
                unconfirmed_count INTEGER NOT NULL DEFAULT 0,
                review_flagged BOOLEAN NOT NULL DEFAULT FALSE,
                details JSON,
                evaluated_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS referral_clicks (
                id SERIAL PRIMARY KEY,
                master_id INTEGER NOT NULL
                    REFERENCES master_profiles(id) ON DELETE CASCADE,
                token VARCHAR(80) NOT NULL UNIQUE,
                clicked_at TIMESTAMPTZ DEFAULT now(),
                expires_at TIMESTAMPTZ NOT NULL,
                used_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                used_at TIMESTAMPTZ
            )
        """))
        bind.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS master_referrals (
                id SERIAL PRIMARY KEY,
                referrer_master_id INTEGER NOT NULL
                    REFERENCES master_profiles(id) ON DELETE CASCADE,
                referred_user_id INTEGER NOT NULL UNIQUE
                    REFERENCES users(id) ON DELETE CASCADE,
                referred_master_id INTEGER UNIQUE
                    REFERENCES master_profiles(id) ON DELETE CASCADE,
                code VARCHAR(16) NOT NULL,
                clicked_at TIMESTAMPTZ NOT NULL,
                registered_at TIMESTAMPTZ DEFAULT now(),
                evaluated_at TIMESTAMPTZ,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                qualified_count INTEGER NOT NULL DEFAULT 0,
                amount NUMERIC(10,2) NOT NULL DEFAULT 0,
                reject_reason VARCHAR(300),
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_master_referrals_referrer_status "
            "ON master_referrals (referrer_master_id, status)"))
    else:
        if not _has_table(bind, 'master_billing_accounts'):
            op.create_table(
                'master_billing_accounts',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('master_id', sa.Integer(), sa.ForeignKey(
                    'master_profiles.id', ondelete='CASCADE'),
                    nullable=False, unique=True),
                sa.Column('trial_started_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('billing_started_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('referral_code', sa.String(16), nullable=False, unique=True),
                sa.Column('access_status', sa.String(20), nullable=False,
                          server_default='trial'),
                sa.Column('review_flag', sa.Boolean(), nullable=False,
                          server_default=sa.false()),
                sa.Column('bonus_blocked_until', sa.DateTime(timezone=True)),
                sa.Column('last_processed_at', sa.DateTime(timezone=True)),
                sa.Column('created_at', sa.DateTime(timezone=True)),
                sa.Column('updated_at', sa.DateTime(timezone=True)),
            )
            op.create_index('ix_billing_accounts_status',
                            'master_billing_accounts', ['access_status'])
        if not _has_table(bind, 'billing_invoices'):
            op.create_table(
                'billing_invoices',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('master_id', sa.Integer(), sa.ForeignKey(
                    'master_profiles.id', ondelete='CASCADE'), nullable=False),
                sa.Column('period_index', sa.Integer(), nullable=False),
                sa.Column('amount', sa.Numeric(10, 2), nullable=False),
                sa.Column('credits_applied', sa.Numeric(10, 2), nullable=False,
                          server_default='0'),
                sa.Column('paid_amount', sa.Numeric(10, 2), nullable=False,
                          server_default='0'),
                sa.Column('status', sa.String(20), nullable=False,
                          server_default='open'),
                sa.Column('issue_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('block_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('period_start', sa.DateTime(timezone=True)),
                sa.Column('period_end', sa.DateTime(timezone=True)),
                sa.Column('paid_at', sa.DateTime(timezone=True)),
                sa.Column('payment_method', sa.String(40)),
                sa.Column('note', sa.Text()),
                sa.Column('notified_at', sa.DateTime(timezone=True)),
                sa.Column('overdue_notified_at', sa.DateTime(timezone=True)),
                sa.Column('reminder_sent_at', sa.DateTime(timezone=True)),
                sa.Column('created_at', sa.DateTime(timezone=True)),
                sa.Column('updated_at', sa.DateTime(timezone=True)),
                sa.UniqueConstraint('master_id', 'period_index',
                                    name='uq_billing_invoice_period'),
            )
            op.create_index('ix_billing_invoices_master_status',
                            'billing_invoices', ['master_id', 'status'])
        if not _has_table(bind, 'billing_credits'):
            op.create_table(
                'billing_credits',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('master_id', sa.Integer(), sa.ForeignKey(
                    'master_profiles.id', ondelete='CASCADE'), nullable=False),
                sa.Column('source', sa.String(30), nullable=False),
                sa.Column('source_ref', sa.String(80)),
                sa.Column('amount', sa.Numeric(10, 2), nullable=False),
                sa.Column('remaining', sa.Numeric(10, 2), nullable=False),
                sa.Column('expires_at', sa.DateTime(timezone=True)),
                sa.Column('expired_at', sa.DateTime(timezone=True)),
                sa.Column('note', sa.Text()),
                sa.Column('created_at', sa.DateTime(timezone=True)),
            )
            op.create_index('ix_billing_credits_master_remaining',
                            'billing_credits', ['master_id', 'remaining'])
        if not _has_table(bind, 'billing_credit_applications'):
            op.create_table(
                'billing_credit_applications',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('credit_id', sa.Integer(), sa.ForeignKey(
                    'billing_credits.id', ondelete='CASCADE'), nullable=False),
                sa.Column('invoice_id', sa.Integer(), sa.ForeignKey(
                    'billing_invoices.id', ondelete='CASCADE'), nullable=False),
                sa.Column('amount', sa.Numeric(10, 2), nullable=False),
                sa.Column('created_at', sa.DateTime(timezone=True)),
                sa.UniqueConstraint('credit_id', 'invoice_id',
                                    name='uq_billing_credit_invoice'),
            )
        if not _has_table(bind, 'billing_payments'):
            op.create_table(
                'billing_payments',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('invoice_id', sa.Integer(), sa.ForeignKey(
                    'billing_invoices.id', ondelete='CASCADE'), nullable=False),
                sa.Column('amount', sa.Numeric(10, 2), nullable=False),
                sa.Column('method', sa.String(40), nullable=False,
                          server_default='manual'),
                sa.Column('note', sa.Text()),
                sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey(
                    'users.id', ondelete='SET NULL')),
                sa.Column('created_at', sa.DateTime(timezone=True)),
            )
        if not _has_table(bind, 'client_bonus_awards'):
            op.create_table(
                'client_bonus_awards',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('master_id', sa.Integer(), sa.ForeignKey(
                    'master_profiles.id', ondelete='CASCADE'),
                    nullable=False, unique=True),
                sa.Column('trial_started_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('eligible_count', sa.Integer(), nullable=False,
                          server_default='0'),
                sa.Column('max_count', sa.Integer(), nullable=False,
                          server_default='10'),
                sa.Column('amount', sa.Numeric(10, 2), nullable=False,
                          server_default='0'),
                sa.Column('status', sa.String(20), nullable=False,
                          server_default='pending'),
                sa.Column('total_candidates', sa.Integer(), nullable=False,
                          server_default='0'),
                sa.Column('unconfirmed_count', sa.Integer(), nullable=False,
                          server_default='0'),
                sa.Column('review_flagged', sa.Boolean(), nullable=False,
                          server_default=sa.false()),
                sa.Column('details', sa.JSON()),
                sa.Column('evaluated_at', sa.DateTime(timezone=True)),
                sa.Column('created_at', sa.DateTime(timezone=True)),
            )
        if not _has_table(bind, 'referral_clicks'):
            op.create_table(
                'referral_clicks',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('master_id', sa.Integer(), sa.ForeignKey(
                    'master_profiles.id', ondelete='CASCADE'), nullable=False),
                sa.Column('token', sa.String(80), nullable=False, unique=True),
                sa.Column('clicked_at', sa.DateTime(timezone=True)),
                sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('used_by_user_id', sa.Integer(), sa.ForeignKey(
                    'users.id', ondelete='SET NULL')),
                sa.Column('used_at', sa.DateTime(timezone=True)),
            )
        if not _has_table(bind, 'master_referrals'):
            op.create_table(
                'master_referrals',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('referrer_master_id', sa.Integer(), sa.ForeignKey(
                    'master_profiles.id', ondelete='CASCADE'), nullable=False),
                sa.Column('referred_user_id', sa.Integer(), sa.ForeignKey(
                    'users.id', ondelete='CASCADE'), nullable=False, unique=True),
                sa.Column('referred_master_id', sa.Integer(), sa.ForeignKey(
                    'master_profiles.id', ondelete='CASCADE'), unique=True),
                sa.Column('code', sa.String(16), nullable=False),
                sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=False),
                sa.Column('registered_at', sa.DateTime(timezone=True)),
                sa.Column('evaluated_at', sa.DateTime(timezone=True)),
                sa.Column('status', sa.String(20), nullable=False,
                          server_default='pending'),
                sa.Column('qualified_count', sa.Integer(), nullable=False,
                          server_default='0'),
                sa.Column('amount', sa.Numeric(10, 2), nullable=False,
                          server_default='0'),
                sa.Column('reject_reason', sa.String(300)),
                sa.Column('created_at', sa.DateTime(timezone=True)),
            )
            op.create_index('ix_master_referrals_referrer_status',
                            'master_referrals',
                            ['referrer_master_id', 'status'])

    # Appointment provenance + visit confirmation.
    _add_column(bind, 'billing_invoices', sa.Column(
        'reminder_sent_at', sa.DateTime(timezone=True), nullable=True))
    _add_column(bind, 'appointments', sa.Column(
        'created_by_role', sa.String(16), nullable=True))
    _add_column(bind, 'appointments', sa.Column(
        'created_by_user_id', sa.Integer(), nullable=True))
    _add_column(bind, 'appointments', sa.Column(
        'visit_confirmation_status', sa.String(16), nullable=True))
    _add_column(bind, 'appointments', sa.Column(
        'visit_prompt_sent_at', sa.DateTime(timezone=True), nullable=True))
    _add_column(bind, 'appointments', sa.Column(
        'visit_confirmation_at', sa.DateTime(timezone=True), nullable=True))
    if pg:
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_appointments_created_by_role "
            "ON appointments (created_by_role)"))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_appointments_visit_confirmation_status "
            "ON appointments (visit_confirmation_status)"))

    # Bell action metadata.
    _add_column(bind, 'notifications', sa.Column(
        'kind', sa.String(32), nullable=True))
    _add_column(bind, 'notifications', sa.Column(
        'appointment_id', sa.Integer(), nullable=True))
    _add_column(bind, 'notifications', sa.Column(
        'resolved_at', sa.DateTime(timezone=True), nullable=True))
    if pg:
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_notifications_kind "
            "ON notifications (kind)"))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_notifications_appointment_id "
            "ON notifications (appointment_id)"))
        bind.execute(sa.text(
            "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS "
            "notifications_appointment_id_fkey"))
        bind.execute(sa.text(
            "ALTER TABLE notifications ADD CONSTRAINT "
            "notifications_appointment_id_fkey FOREIGN KEY (appointment_id) "
            "REFERENCES appointments(id) ON DELETE SET NULL"))

    # Existing masters start on a fresh 14-day ladder.
    # The production superuser (user id=1) is not a billable master and must
    # stay untouched even though a MasterProfile exists for admin tooling.
    if pg:
        bind.execute(sa.text(
            "UPDATE master_profiles SET tariff = 'trial', "
            "trial_ends_at = now() + interval '14 days' "
            "WHERE user_id <> 1"))
    else:
        bind.execute(sa.text(
            "UPDATE master_profiles SET tariff = 'trial', "
            "trial_ends_at = datetime('now', '+14 days') "
            "WHERE user_id <> 1"))


def downgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == 'postgresql'
    if pg:
        bind.execute(sa.text(
            "ALTER TABLE notifications DROP CONSTRAINT IF EXISTS "
            "notifications_appointment_id_fkey"))
        bind.execute(sa.text("DROP INDEX IF EXISTS ix_notifications_kind"))
        bind.execute(sa.text(
            "DROP INDEX IF EXISTS ix_appointments_created_by_role"))
        bind.execute(sa.text(
            "DROP INDEX IF EXISTS ix_appointments_visit_confirmation_status"))
        for table in (
            'master_referrals', 'referral_clicks', 'client_bonus_awards',
            'billing_payments', 'billing_credit_applications',
            'billing_credits', 'billing_invoices',
            'master_billing_accounts',
        ):
            bind.execute(sa.text(f'DROP TABLE IF EXISTS {table} CASCADE'))
        for col in ('kind', 'appointment_id', 'resolved_at'):
            bind.execute(sa.text(
                f'ALTER TABLE notifications DROP COLUMN IF EXISTS {col}'))
        for col in ('created_by_role', 'created_by_user_id',
                    'visit_confirmation_status', 'visit_prompt_sent_at',
                    'visit_confirmation_at'):
            bind.execute(sa.text(
                f'ALTER TABLE appointments DROP COLUMN IF EXISTS {col}'))
    else:
        for table in (
            'master_referrals', 'referral_clicks', 'client_bonus_awards',
            'billing_payments', 'billing_credit_applications',
            'billing_credits', 'billing_invoices',
            'master_billing_accounts',
        ):
            if _has_table(bind, table):
                op.drop_table(table)
        with op.batch_alter_table('notifications') as batch:
            for col in ('kind', 'appointment_id', 'resolved_at'):
                if col in _columns(bind, 'notifications'):
                    batch.drop_column(col)
        with op.batch_alter_table('appointments') as batch:
            for col in ('created_by_role', 'created_by_user_id',
                        'visit_confirmation_status', 'visit_prompt_sent_at',
                        'visit_confirmation_at'):
                if col in _columns(bind, 'appointments'):
                    batch.drop_column(col)
