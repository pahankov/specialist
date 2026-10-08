"""Tests for pull_production upsert logic (no network; in-memory SQLite)."""
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.utils.security import hash_password, verify_password
from pull_production import (
    dt_parse,
    prune_backups,
    upsert_client,
    upsert_master,
    upsert_working_hour,
)

DEV_HASH = hash_password("DevPass123!")


@pytest_asyncio.fixture(scope="function")
async def psession():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


def master_row(**over):
    row = {
        "id": 10, "user_id": 20, "name": "Elena", "email": "elena@example.com",
        "phone": "+79990001111", "telegram_username": None, "description": "top",
        "status": "active", "is_active": True, "is_admin": False,
        "created_at": "2026-01-01T10:00:00+00:00", "updated_at": None,
    }
    row.update(over)
    return row


class TestUpsertMaster:
    async def test_creates_user_and_profile_with_prod_ids(self, psession):
        c = {"created": 0, "updated": 0, "users_created": 0, "users_updated": 0}
        await upsert_master(psession, master_row(), DEV_HASH, c)
        await psession.commit()

        user = await psession.get(User, 20)
        assert user is not None and user.email == "elena@example.com"
        assert verify_password("DevPass123!", user.hashed_password) is True
        profile = await psession.get(MasterProfile, 10)
        assert profile is not None and profile.user_id == 20
        assert c["created"] == 1 and c["users_created"] == 1

    async def test_rerun_updates_without_duplicates(self, psession):
        c = {"created": 0, "updated": 0, "users_created": 0, "users_updated": 0}
        await upsert_master(psession, master_row(), DEV_HASH, c)
        await upsert_master(psession, master_row(name="Elena V."), DEV_HASH, c)
        await psession.commit()

        from sqlalchemy import func, select
        n = (await psession.execute(select(func.count(User.id)))).scalar()
        assert n == 1
        user = await psession.get(User, 20)
        assert user.name == "Elena V."
        assert c["updated"] == 1 and c["users_updated"] == 1


class TestUpsertClient:
    def client_row(self, **over):
        row = {"id": 30, "name": "Ivan", "phone": "+79990002222",
               "email": "ivan@example.com", "no_show_count": 2,
               "created_at": None, "updated_at": None}
        row.update(over)
        return row

    async def test_creates_user_profile_and_no_show(self, psession):
        c = {"created": 0, "updated": 0, "users_created": 0,
             "users_updated": 0, "skipped": 0}
        await upsert_client(psession, self.client_row(), DEV_HASH, c)
        await psession.commit()

        user = await psession.get(User, 30)
        assert user is not None and user.role.value == "CLIENT"
        from sqlalchemy import select
        prof = (await psession.execute(
            select(ClientProfile).where(ClientProfile.user_id == 30)
        )).scalar_one()
        assert prof.no_show_count == 2
        assert c["created"] == 1

    async def test_email_conflict_skips_row(self, psession):
        from app.models.user import UserRole
        psession.add(User(id=99, name="Local", email="ivan@example.com",
                          phone="+79990009999", hashed_password=DEV_HASH,
                          role=UserRole.CLIENT))
        await psession.commit()
        c = {"created": 0, "updated": 0, "users_created": 0,
             "users_updated": 0, "skipped": 0}
        await upsert_client(psession, self.client_row(), DEV_HASH, c)
        assert c["skipped"] == 1
        assert await psession.get(User, 30) is None


class TestUpsertWorkingHour:
    async def test_parses_date_and_time(self, psession):
        c = {"created": 0, "updated": 0}
        await upsert_working_hour(psession, {
            "id": 5, "master_id": 10, "schedule_date": "2026-10-09",
            "start_time": "09:00:00", "end_time": "18:00:00", "is_active": True,
        }, c)
        await psession.commit()

        from app.models.working_hour import WorkingHour
        wh = await psession.get(WorkingHour, 5)
        assert wh is not None
        assert wh.schedule_date.isoformat() == "2026-10-09"
        assert wh.start_time.hour == 9 and wh.end_time.hour == 18
        assert c["created"] == 1


class TestDtParse:
    def test_aware_to_naive_utc(self):
        dt = dt_parse("2026-01-01T12:00:00+03:00")
        assert dt.tzinfo is None
        assert (dt.hour, dt.day) == (9, 1)

    def test_none_passthrough(self):
        assert dt_parse(None) is None


class TestPruneBackups:
    def test_keeps_newest_n(self, tmp_path):
        db = str(tmp_path / "test.db")
        open(db, "w").close()
        names = []
        for tag in ("1", "2", "3", "4"):
            p = tmp_path / f"test.db.bak-2026010{tag}-000000"
            p.write_text("x")
            names.append(str(p))
        removed = prune_backups(db, keep=2)
        assert len(removed) == 2
        import glob as _glob
        left = sorted(_glob.glob(f"{db}.bak-*"))
        assert [n.split("bak-")[-1] for n in left] == ["20260103-000000", "20260104-000000"]

    def test_missing_db_is_noop(self, tmp_path):
        assert prune_backups(str(tmp_path / "nope.db"), keep=5) == []
