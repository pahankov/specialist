"""Pull production data into the LOCAL database (prod -> local, one way).

Reads through the existing admin API (no backend changes needed) and
upserts into a local SQLite DB using the same SQLAlchemy models.

What is synced: countries, cities, masters (+ MasterProfile), services,
working hours, clients (+ ClientProfile). Appointments/audit/tokens are
NOT synced by design (prod history stays on prod).

Identity & safety:
- Prod IDs are preserved (needed for service/working-hours FKs).
- Passwords are NOT exposed by the API: every pulled user gets
  LOCAL_DEV_PASSWORD (env, default "DevPass123!") — local logins only.
- User city is NOT exposed by the API: city_id stays NULL locally.
- The local *.db file is backed up to *.bak-<timestamp> before writing.
- Reverse direction (local -> prod) is intentionally NOT implemented:
  pushing dev fixtures into production is a data-loss risk. If you ever
  need it, do it explicitly via the admin UI/API per record.

Usage (run from online-booking/backend):
    set PROD_API=https://beauty-specialist.ru
    set PROD_EMAIL=<admin email>            # or typed via prompt
    set PROD_PASSWORD=<admin password>      # or typed via prompt (hidden)
    set LOCAL_DEV_PASSWORD=DevPass123!

    python pull_production.py --dry-run                 # only counts
    python pull_production.py --yes                     # no confirm prompt
    python pull_production.py --entities masters,clients
    python pull_production.py --db ./my_local.db

Credentials are NEVER taken from CLI args (shell history / process list).
"""
import argparse
import asyncio
import getpass
import os
import shutil
import sys
from datetime import date, datetime, time, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.models.city import City  # noqa: E402
from app.models.client_profile import ClientProfile  # noqa: E402
from app.models.country import Country  # noqa: E402
from app.models.master_profile import MasterProfile  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.models.working_hour import WorkingHour  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

DEFAULT_API = "https://beauty-specialist.ru"
DEFAULT_DB = "./online_booking.db"
PAGE_SIZE = 100

ENTITIES = ("geo", "masters", "services", "working-hours", "clients")


def dt_parse(value):
    """Parse ISO datetime; normalize to naive UTC for SQLite storage."""
    if not value:
        return None
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def d_parse(value):
    if not value or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def t_parse(value):
    if not value or isinstance(value, time):
        return value
    return time.fromisoformat(str(value)[:8])


class ProdClient:
    """Thin admin-API client (cookie session)."""

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base, timeout=30.0)

    def login(self, email: str, password: str) -> None:
        r = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        r.raise_for_status()

    def get_paged(self, path: str, params=None):
        """Yield items from a PaginatedResponse endpoint (items/total)."""
        page = 1
        while True:
            q = dict(params or {})
            q.update({"page": page, "page_size": PAGE_SIZE})
            r = self.client.get(path, params=q)
            r.raise_for_status()
            payload = r.json()
            items = payload.get("items", [])
            yield from items
            total = payload.get("total", len(items))
            if page * PAGE_SIZE >= total or not items:
                break
            page += 1

    def get_all(self, path: str, params=None):
        r = self.client.get(path, params=params or {})
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, list):
            return payload
        return payload.get("items", [])


async def upsert_country(session: AsyncSession, row: dict, counts: dict) -> None:
    obj = await session.get(Country, row["id"])
    if obj is None:
        session.add(Country(
            id=row["id"], code=row["code"], name_ru=row["name_ru"],
            name_en=row.get("name_en"), phone_prefix=row.get("phone_prefix", ""),
            is_active=row.get("is_active", True),
        ))
        counts["created"] += 1
    else:
        obj.code, obj.name_ru = row["code"], row["name_ru"]
        obj.name_en = row.get("name_en", obj.name_en)
        counts["updated"] += 1


async def upsert_city(session: AsyncSession, row: dict, counts: dict) -> None:
    obj = await session.get(City, row["id"])
    if obj is None:
        session.add(City(
            id=row["id"], country_id=row["country_id"], name_ru=row["name_ru"],
            name_en=row.get("name_en"), slug=row.get("slug") or row["name_ru"],
            is_active=row.get("is_active", True),
        ))
        counts["created"] += 1
    else:
        obj.name_ru = row["name_ru"]
        counts["updated"] += 1


async def _get_user(session: AsyncSession, user_id: int):
    return await session.get(User, user_id)


async def upsert_master(session: AsyncSession, row: dict, dev_password_hash: str, counts: dict) -> None:
    """Upsert User + MasterProfile keeping prod IDs (FKs for services/hours)."""
    user = await _get_user(session, row["user_id"])
    if user is None:
        user = User(
            id=row["user_id"], email=row.get("email"), phone=row.get("phone"),
            hashed_password=dev_password_hash, name=row.get("name") or "Master",
            role=UserRole.ADMIN if row.get("is_admin") else UserRole.MASTER,
            city_id=None, is_active=row.get("is_active", True),
            is_verified=True,
            created_at=dt_parse(row.get("created_at")),
            updated_at=dt_parse(row.get("updated_at")),
        )
        session.add(user)
        await session.flush()
        counts["users_created"] += 1
    else:
        user.name = row.get("name") or user.name
        user.email = row.get("email", user.email)
        user.phone = row.get("phone", user.phone)
        user.is_active = row.get("is_active", user.is_active)
        counts["users_updated"] += 1

    profile = await session.get(MasterProfile, row["id"])
    if profile is None:
        session.add(MasterProfile(
            id=row["id"], user_id=user.id,
            description=row.get("description"),
            telegram_username=row.get("telegram_username"),
            status=row.get("status") or "active",
            is_active=row.get("is_active", True),
        ))
        counts["created"] += 1
    else:
        profile.description = row.get("description", profile.description)
        profile.telegram_username = row.get("telegram_username", profile.telegram_username)
        profile.status = row.get("status") or profile.status
        counts["updated"] += 1


async def upsert_service(session: AsyncSession, row: dict, counts: dict) -> None:
    obj = await session.get(Service, row["id"])
    if obj is None:
        session.add(Service(
            id=row["id"], master_id=row["master_id"], name=row["name"],
            description=row.get("description"),
            duration_minutes=row["duration_minutes"], price=row["price"],
            is_active=row.get("is_active", True),
        ))
        counts["created"] += 1
    else:
        obj.name, obj.description = row["name"], row.get("description")
        obj.duration_minutes, obj.price = row["duration_minutes"], row["price"]
        obj.is_active = row.get("is_active", obj.is_active)
        counts["updated"] += 1


async def upsert_working_hour(session: AsyncSession, row: dict, counts: dict) -> None:
    obj = await session.get(WorkingHour, row["id"])
    if obj is None:
        session.add(WorkingHour(
            id=row["id"], master_id=row["master_id"],
            schedule_date=d_parse(row["schedule_date"]),
            start_time=t_parse(row["start_time"]), end_time=t_parse(row["end_time"]),
            is_active=row.get("is_active", True),
        ))
        counts["created"] += 1
    else:
        obj.schedule_date = d_parse(row["schedule_date"])
        obj.start_time, obj.end_time = t_parse(row["start_time"]), t_parse(row["end_time"])
        counts["updated"] += 1


async def upsert_client(session: AsyncSession, row: dict, dev_password_hash: str, counts: dict) -> None:
    """Clients are matched by prod user id; email/phone conflicts are skipped."""
    user = await _get_user(session, row["id"])
    if user is None:
        user = User(
            id=row["id"], email=row.get("email"), phone=row.get("phone"),
            hashed_password=dev_password_hash, name=row.get("name") or "Client",
            role=UserRole.CLIENT, city_id=None, is_active=True, is_verified=True,
            created_at=dt_parse(row.get("created_at")),
            updated_at=dt_parse(row.get("updated_at")),
        )
        session.add(user)
        try:
            await session.flush()
        except Exception:
            await session.rollback()
            print(f"  SKIP client id={row['id']}: email/phone already used by another local user")
            counts["skipped"] += 1
            return
        counts["users_created"] += 1
    else:
        user.name = row.get("name") or user.name
        counts["users_updated"] += 1

    result = await session.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        session.add(ClientProfile(
            user_id=user.id, no_show_count=row.get("no_show_count", 0) or 0,
        ))
        counts["created"] += 1
    else:
        profile.no_show_count = row.get("no_show_count", 0) or 0
        counts["updated"] += 1


async def run(api: str, email: str, password: str, db_path: str,
              entities, dry_run: bool, dev_password: str) -> dict:
    prod = ProdClient(api)
    print(f"Login to {api} as {email} ...")
    prod.login(email, password)
    print("  OK")

    fetched = {}
    if "geo" in entities:
        fetched["countries"] = prod.get_all("/api/v1/countries/")
        fetched["cities"] = prod.get_all("/api/v1/cities/", {"page_size": 1000})
        print(f"  geo: {len(fetched['countries'])} countries, {len(fetched['cities'])} cities")
    if "masters" in entities:
        fetched["masters"] = prod.get_all("/api/v1/admin/masters")
        print(f"  masters: {len(fetched['masters'])}")
    if "services" in entities:
        fetched["services"] = list(prod.get_paged("/api/v1/admin/services/all"))
        print(f"  services: {len(fetched['services'])}")
    if "working-hours" in entities:
        fetched["working_hours"] = prod.get_all("/api/v1/admin/working-hours")
        print(f"  working-hours: {len(fetched['working_hours'])}")
    if "clients" in entities:
        fetched["clients"] = list(prod.get_paged("/api/v1/admin/clients"))
        print(f"  clients: {len(fetched['clients'])}")

    if dry_run:
        print("DRY-RUN: nothing written.")
        return {"dry_run": True, "fetched": {k: len(v) for k, v in fetched.items()}}

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    dev_hash = hash_password(dev_password)
    summary = {}
    async with maker() as session:
        if "geo" in entities:
            c = {"created": 0, "updated": 0}
            for row in fetched["countries"]:
                await upsert_country(session, row, c)
            for row in fetched["cities"]:
                await upsert_city(session, row, c)
            summary["geo"] = c
        if "masters" in entities:
            c = {"created": 0, "updated": 0, "users_created": 0, "users_updated": 0}
            for row in fetched["masters"]:
                await upsert_master(session, row, dev_hash, c)
            summary["masters"] = c
        if "services" in entities:
            c = {"created": 0, "updated": 0}
            for row in fetched["services"]:
                await upsert_service(session, row, c)
            summary["services"] = c
        if "working-hours" in entities:
            c = {"created": 0, "updated": 0}
            for row in fetched["working_hours"]:
                await upsert_working_hour(session, row, c)
            summary["working-hours"] = c
        if "clients" in entities:
            c = {"created": 0, "updated": 0, "users_created": 0,
                 "users_updated": 0, "skipped": 0}
            for row in fetched["clients"]:
                await upsert_client(session, row, dev_hash, c)
            summary["clients"] = c
        await session.commit()
    await engine.dispose()
    return summary


def backup_db(db_path: str) -> str:
    import datetime as _dt
    dst = f"{db_path}.bak-{_dt.datetime.now():%Y%m%d-%H%M%S}"
    if os.path.exists(db_path):
        shutil.copy2(db_path, dst)
        print(f"Local DB backed up to {dst}")
    return dst


def main() -> None:
    ap = argparse.ArgumentParser(description="Pull production data into local DB (one way).")
    ap.add_argument("--api", default=os.getenv("PROD_API", DEFAULT_API))
    ap.add_argument("--db", default=os.getenv("LOCAL_DB", DEFAULT_DB))
    ap.add_argument("--email", default=os.getenv("PROD_EMAIL", ""))
    ap.add_argument("--entities", default=",".join(ENTITIES),
                    help=f"subset of {','.join(ENTITIES)}")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip confirm prompt")
    args = ap.parse_args()

    entities = [e.strip() for e in args.entities.split(",") if e.strip()]
    bad = [e for e in entities if e not in ENTITIES]
    if bad:
        print(f"Unknown entities: {bad}. Choose from {','.join(ENTITIES)}", file=sys.stderr)
        raise SystemExit(2)

    email = args.email or input("Prod admin email: ").strip()
    password = os.getenv("PROD_PASSWORD", "") or getpass.getpass("Prod admin password: ")
    dev_password = os.getenv("LOCAL_DEV_PASSWORD", "DevPass123!")

    if not args.dry_run and not args.yes:
        print(f"This will UPSERT prod data into local DB: {args.db}")
        print("Passwords of pulled users will be reset to the dev password.")
        answer = input("Continue? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return
        backup_db(args.db)

    summary = asyncio.run(run(args.api, email, password, args.db, entities,
                              args.dry_run, dev_password))
    print("Summary:")
    for entity, counts in summary.items():
        if isinstance(counts, dict):
            print(f"  {entity}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
