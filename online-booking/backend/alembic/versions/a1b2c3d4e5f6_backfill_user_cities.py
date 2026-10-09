"""backfill cities for users without one (Moscow/SPb/Krasnodar round-robin)

Revision ID: a1b2c3d4e5f6
Revises: f9b3c1d4e5a6
Create Date: 2026-10-09

Test data has thousands of users with NULL city_id. Assign Moscow,
Saint Petersburg, Krasnodar round-robin by user id (NULLs only —
never touches already-set cities). Idempotent.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f9b3c1d4e5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CITIES = ('Москва', 'Санкт-Петербург', 'Краснодар')


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(text("SELECT id, name_ru FROM cities")).fetchall()
    by_name = {r[1]: r[0] for r in rows}
    ordered = [by_name[n] for n in _CITIES if n in by_name]
    if not ordered:
        return
    for i, city_id in enumerate(ordered):
        conn.execute(
            text("UPDATE users SET city_id = :cid WHERE city_id IS NULL AND (id % :n) = :m"),
            {"cid": city_id, "n": len(ordered), "m": i},
        )


def downgrade() -> None:
    # Backfill is not reversible (original NULLs unknown) — no-op.
    pass
