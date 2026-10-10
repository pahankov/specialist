"""Fix production database issues using async SQLAlchemy.

This script:
1. Creates countries and cities if they don't exist
2. Verifies superuser exists and has ADMIN role
3. Creates MasterProfile for superuser if missing

Uses the same database connection as the main app.

Usage:
    python fix_production_db.py

Environment:
    DATABASE_URL - PostgreSQL connection string (reads from .env if not set)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.country import Country
from app.models.city import City
from app.utils.security import hash_password
from sqlalchemy import select



async def fix_geography(session):
    """Canonical geography top-up (delegates to seed_common)."""
    from seed_common import ensure_geography
    print("\n  Checking geography data...")
    await ensure_geography(session)

async def fix_superuser(session, email, password):
    """Verify superuser (delegates to create_superuser.ensure_superuser).

    Kept as a thin wrapper: deploy.yml and tests import this name.
    password=None keeps the existing hash (routine deploys must never
    reset the production password to a placeholder).
    """
    from create_superuser import ensure_superuser
    print("  Checking superuser...")
    return await ensure_superuser(session, email, password)




async def main():
    DATABASE_URL = os.environ.get("DATABASE_URL", "Not set")
    # Credentials ONLY from env (server .env / Secrets) — never hardcoded:
    # a scrubbed placeholder here would silently reset the prod password.
    SUPERUSER_EMAIL = os.getenv("SUPERUSER_EMAIL", "")
    SUPERUSER_PASSWORD = os.getenv("SUPERUSER_PASSWORD") or None
    if not SUPERUSER_EMAIL:
        print("WARNING: SUPERUSER_EMAIL not set - skipping superuser check (exit 0).")
        return

    print(f"Connecting to: {DATABASE_URL}")
    
    async with AsyncSessionLocal() as session:
        await fix_geography(session)
        user = await fix_superuser(session, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        
        print("\n" + "="*60)
        print("✅ All fixes applied successfully!")
        print("="*60)
        print(f"\nSuperuser credentials:")
        print(f"  Email: {SUPERUSER_EMAIL or '<not set>'}")
        print(f"  Password: {'<set>' if SUPERUSER_PASSWORD else '<kept>'}")
        print(f"  Role: {user.role.value}")
        print(f"  Admin: {user.role == UserRole.ADMIN}")
        print(f"\nGo to https://beauty-specialist.ru and login!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
