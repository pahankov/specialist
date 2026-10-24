#!/bin/bash
# Database stage of the deploy: schema fix -> ownership -> alembic -> seed scripts.
# Called from .github/workflows/deploy.yml with the repo root as $1.
# Requires DATABASE_URL exported by the caller. Mirrors script_stop:true -> set -e.
set -e

ROOT="${1:?usage: bash scripts/deploy_db.sh /var/www/beauty-specialist}"
BACKEND_DIR="$ROOT/online-booking/backend"
cd "$BACKEND_DIR"

# Resolve DATABASE_URL the same way the deploy does: exported env wins, else
# read ONLY that key from the server .env (never `source` the whole file).
if [ -z "${DATABASE_URL:-}" ] && [ -f "$BACKEND_DIR/.env" ]; then
  DATABASE_URL=$(sed -E -n 's/^[[:space:]]*(export[[:space:]]+)?DATABASE_URL[[:space:]]*=[[:space:]]*//p' "$BACKEND_DIR/.env" | tail -n 1 | sed -e "s/^[\"']//" -e "s/[\"']$//")
fi
# Alembic imports app.database and needs an async driver even if .env or an
# operator supplied a plain postgresql:// URL.
if [ -n "${DATABASE_URL:-}" ]; then
  DATABASE_URL=$(printf '%s' "$DATABASE_URL" | sed -E 's#^postgresql(\+[a-z0-9_]+)?://#postgresql+asyncpg://#')
  export DATABASE_URL
fi

# Derive the local database name from the URL instead of hardcoding
# `online_booking`: staging copies and renamed prod DBs must work too.
DB_NAME=""
if [ -n "${DATABASE_URL:-}" ]; then
  DB_NAME="${DATABASE_URL%%\?*}"
  DB_NAME="${DB_NAME%%#*}"
  DB_NAME="${DB_NAME##*/}"
fi
if [ -z "$DB_NAME" ]; then
  DB_NAME=online_booking
  echo "[WARN] DATABASE_URL has no database name; falling back to $DB_NAME"
fi
if ! printf '%s' "$DB_NAME" | grep -Eq '^[A-Za-z0-9_]+$'; then
  echo "ERROR: unsafe database name derived from DATABASE_URL: $DB_NAME"
  exit 1
fi
echo "Target database: $DB_NAME"

# fix_all_tables.sql is FROZEN: it contains DROP COLUMN and runs destructive
# DDL against production. The schema is managed by Alembic only; the file is
# kept for manual emergency recovery, never for routine deploys.
echo "=== SCHEMA FIX (SKIPPED) ==="
echo "fix_all_tables.sql is manual-only; schema changes go through Alembic"

# Fix table ownership (tables created by postgres, migrations run as specialist)
# Single-table ALTER fails every new migration otherwise (see DEPLOYMENT_RULES#5)
echo "=== FIX TABLE OWNERSHIP ==="
for tbl in users master_profiles client_profiles services appointments working_hours blocked_slots reviews refresh_tokens audit_logs countries cities otp_codes notifications notification_preferences pnl_categories pnl_incomes pnl_expenses; do
  sudo -u postgres psql -d "$DB_NAME" -c "ALTER TABLE ${tbl} OWNER TO specialist;" 2>/dev/null || echo "[WARN] Ownership fix skipped for ${tbl}"
done
echo "=== OWNERSHIP DONE ==="

# Squash (1.13.0): single baseline 5280b944554f replaced the 12-file chain.
# A prod DB stamped at the old head carries the same schema the backend
# already runs on, so mark it as baseline and `upgrade head` becomes a
# no-op. Fresh DBs have no
# alembic_version row -> plain `upgrade head` builds everything.
# NOTE: plain `alembic stamp X` does NOT work here — it tries to resolve
# the DB's current revision (b2c3d4e5f6a7) in the versions directory,
# where the old files no longer exist ("Can't locate revision").
# So delete the version row first, then stamp the empty table.
echo "=== ALEMBIC ==="
OLD_HEAD=$(sudo -u postgres psql -d "$DB_NAME" -tAc "SELECT version_num FROM alembic_version" 2>/dev/null | tr -d '[:space:]' || true)
if [ "$OLD_HEAD" = "b2c3d4e5f6a7" ]; then
  echo "Old migration chain detected - resetting version to squashed baseline..."
  sudo -u postgres psql -d "$DB_NAME" -c "DELETE FROM alembic_version;"
  DATABASE_URL="${DATABASE_URL}" alembic stamp 5280b944554f
fi
DATABASE_URL="${DATABASE_URL}" alembic upgrade head
echo "=== ALEMBIC DONE ==="

echo "=== SUPERUSER ==="
DATABASE_URL="${DATABASE_URL}" python3.12 create_superuser.py
echo "=== SUPERUSER DONE ==="

echo "=== FIX DB ==="
DATABASE_URL="${DATABASE_URL}" python3.12 fix_production_db.py
echo "=== FIX DB DONE ==="

echo "=== FIX MASTERS ==="
DATABASE_URL="${DATABASE_URL}" python3.12 fix_production_masters.py
echo "=== FIX MASTERS DONE ==="

echo "=== SEED ==="
DATABASE_URL="${DATABASE_URL}" python3.12 seed_production.py
echo "=== SEED DONE ==="

echo "=== SEED CITIES (idempotent top-up) ==="
DATABASE_URL="${DATABASE_URL}" python3.12 seed_cities.py
echo "=== SEED CITIES DONE ==="

# Demo seeding (create_minimal_reviews.py) is NOT run in prod since 1.79.1:
# it writes only into empty tables, and after the pre-launch wipe a deploy
# would re-inject 3 sample masters + 5 clients + 10 appointments/reviews.
# The script stays in the repo for local/dev stands — run it manually there.
