#!/bin/bash
# Database stage of the deploy: schema fix -> ownership -> alembic -> seed scripts.
# Called from .github/workflows/deploy.yml with the repo root as $1.
# Requires DATABASE_URL exported by the caller. Mirrors script_stop:true -> set -e.
set -e

ROOT="${1:?usage: bash scripts/deploy_db.sh /var/www/beauty-specialist}"
cd "$ROOT/online-booking/backend"

# Fix schema mismatches BEFORE migrations (uses file in current directory)
sudo -u postgres psql -d online_booking -f fix_all_tables.sql || echo "[WARN] Schema fix failed, continuing..."

# Fix table ownership (tables created by postgres, migrations run as specialist)
# Single-table ALTER fails every new migration otherwise (see DEPLOYMENT_RULES#5)
echo "=== FIX TABLE OWNERSHIP ==="
for tbl in users master_profiles client_profiles services appointments working_hours blocked_slots reviews refresh_tokens audit_logs countries cities otp_codes; do
  sudo -u postgres psql -d online_booking -c "ALTER TABLE ${tbl} OWNER TO specialist;" 2>/dev/null || echo "[WARN] Ownership fix skipped for ${tbl}"
done
echo "=== OWNERSHIP DONE ==="

# Squash (1.13.0): single baseline 5280b944554f replaced the 12-file chain.
# A prod DB stamped at the old head carries the same schema the backend
# already runs on (plus idempotent fix_all_tables.sql above), so mark it
# as baseline and `upgrade head` becomes a no-op. Fresh DBs have no
# alembic_version row -> plain `upgrade head` builds everything.
# NOTE: plain `alembic stamp X` does NOT work here — it tries to resolve
# the DB's current revision (b2c3d4e5f6a7) in the versions directory,
# where the old files no longer exist ("Can't locate revision").
# So delete the version row first, then stamp the empty table.
echo "=== ALEMBIC ==="
OLD_HEAD=$(sudo -u postgres psql -d online_booking -tAc "SELECT version_num FROM alembic_version" 2>/dev/null | tr -d '[:space:]' || true)
if [ "$OLD_HEAD" = "b2c3d4e5f6a7" ]; then
  echo "Old migration chain detected - resetting version to squashed baseline..."
  sudo -u postgres psql -d online_booking -c "DELETE FROM alembic_version;"
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

echo "=== MINIMAL REVIEWS ==="
DATABASE_URL="${DATABASE_URL}" python3.12 create_minimal_reviews.py
echo "=== MINIMAL REVIEWS DONE ==="
