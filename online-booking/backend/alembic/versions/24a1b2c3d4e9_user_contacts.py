"""user_contacts: multi-contact account model (phones/emails with flags).

Phone/email stop being scalar columns on users: every account gets a set of
contacts, each with its own verification level. users.phone / users.email stay
for the transition; this migration backfills the new table so the unified
login entry (1.79.0) can already search by contact value.

Backfill rules (see LOCAL.md «Единый вход», design items 1/5):
- emails are copied from users.email, lowercased;
- phones are copied from users.phone, normalized to "+7 (XXX) XXX-XX-XX";
- a contact is marked verified_via="social" only when the account provably
  got it from a social provider: email on an account with a social binding
  (vk/yandex/max) that carries users.is_verified, phone of a MAX-bound account
  (max_user_id — the number was proven by the HMAC-confirmed contact share).
  Password-only accounts land as "не подтверждён" (design: парольные аккаунты
  — без верификаций).
- collisions after normalization (one value on two accounts) and invalid
  phones are skipped with a warning: the lowest-id account wins.

Idempotent: CREATE ... IF NOT EXISTS + inserts ignore already-present rows.
"""
import re
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24a1b2c3d4e9'
down_revision: str = '23a1b2c3d4e8'
branch_labels = None
depends_on = None


def _normalize_phone(raw: str) -> str:
    """Standalone frozen copy of app.utils.phone.normalize_phone — migrations
    must not depend on app code that may evolve later."""
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        raise ValueError("empty")
    if len(digits) > 11:
        digits = digits[-11:]
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if not digits.startswith("7"):
        digits = "7" + digits
    if len(digits) != 11:
        raise ValueError("not 11 digits")
    return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def _create_table(bind) -> None:
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(
            "CREATE TABLE IF NOT EXISTS user_contacts ("
            "id SERIAL PRIMARY KEY, "
            "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
            "contact_type VARCHAR(10) NOT NULL, "
            "value VARCHAR(255) NOT NULL, "
            "is_verified BOOLEAN NOT NULL DEFAULT FALSE, "
            "verified_via VARCHAR(16), "
            "verified_at TIMESTAMPTZ, "
            "is_primary BOOLEAN NOT NULL DEFAULT FALSE, "
            "created_at TIMESTAMPTZ, "
            "updated_at TIMESTAMPTZ)"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_user_contacts_user_id "
            "ON user_contacts (user_id)"
        ))
        bind.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_contacts_type_value "
            "ON user_contacts (contact_type, value)"
        ))
    else:
        if "user_contacts" not in sa.inspect(bind).get_table_names():
            op.create_table(
                "user_contacts",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(),
                          sa.ForeignKey("users.id", ondelete="CASCADE"),
                          nullable=False),
                sa.Column("contact_type", sa.String(10), nullable=False),
                sa.Column("value", sa.String(255), nullable=False),
                sa.Column("is_verified", sa.Boolean(), nullable=False,
                          server_default=sa.text("0")),
                sa.Column("verified_via", sa.String(16), nullable=True),
                sa.Column("verified_at", sa.DateTime(timezone=True),
                          nullable=True),
                sa.Column("is_primary", sa.Boolean(), nullable=False,
                          server_default=sa.text("0")),
                sa.Column("created_at", sa.DateTime(timezone=True),
                          nullable=True),
                sa.Column("updated_at", sa.DateTime(timezone=True),
                          nullable=True),
            )
            op.create_index("ix_user_contacts_user_id", "user_contacts",
                            ["user_id"], unique=False)
            op.create_index("ix_user_contacts_type_value", "user_contacts",
                            ["contact_type", "value"], unique=True)


def _backfill(bind) -> None:
    rows = bind.execute(sa.text(
        "SELECT id, email, phone, is_verified, "
        "vk_user_id, yandex_user_id, max_user_id FROM users ORDER BY id"
    )).fetchall()

    on_pg = bind.dialect.name == "postgresql"
    now = datetime.now(timezone.utc)
    taken = set()
    inserted = skipped = 0

    for uid, email, phone, is_verified, vk_id, ya_id, max_id in rows:
        has_social = any(v is not None for v in (vk_id, ya_id, max_id))
        candidates = []
        if email:
            val = email.strip().lower()
            if val:
                candidates.append(("email", val,
                                   bool(is_verified and has_social)))
        if phone:
            try:
                val = _normalize_phone(phone)
            except ValueError:
                print(f"[user_contacts] skip unparsable phone "
                      f"user_id={uid}: {phone!r}")
                skipped += 1
                val = None
            if val:
                candidates.append(("phone", val, max_id is not None))

        # Телефон приоритетнее почты (design §3): он встаёт первым и получает
        # is_primary при прочих равных.
        ordered = ([c for c in candidates if c[0] == "phone"]
                   + [c for c in candidates if c[0] == "email"])
        resolved = []
        for ctype, val, verified in ordered:
            key = (ctype, val)
            if key in taken:
                print(f"[user_contacts] skip duplicate {ctype} "
                      f"user_id={uid}: {val}")
                skipped += 1
                continue
            taken.add(key)
            resolved.append((ctype, val, verified))

        primary_types = set()
        for ctype, val, verified in resolved:
            is_primary = ctype not in primary_types
            primary_types.add(ctype)
            sql = (
                "INSERT INTO user_contacts "
                "(user_id, contact_type, value, is_verified, verified_via, "
                "verified_at, is_primary, created_at, updated_at) "
                "VALUES (:uid, :ctype, :val, :ver, :via, :vat, :prim, "
                ":now, :now)"
            )
            if on_pg:
                sql += " ON CONFLICT DO NOTHING"
            else:
                sql = sql.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
            result = bind.execute(sa.text(sql), {
                "uid": uid, "ctype": ctype, "val": val,
                "ver": verified,
                "via": "social" if verified else None,
                "vat": now if verified else None,
                "prim": is_primary,
                "now": now,
            })
            if result.rowcount:
                inserted += 1
            else:
                skipped += 1

    print(f"[user_contacts] backfill done: inserted={inserted}, "
          f"skipped={skipped}, scanned_users={len(rows)}")


def upgrade() -> None:
    bind = op.get_bind()
    _create_table(bind)
    _backfill(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("DROP TABLE IF EXISTS user_contacts"))
    else:
        if "user_contacts" in sa.inspect(bind).get_table_names():
            op.drop_table("user_contacts")
