"""Notification preferences, external dispatch and background reminders."""
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.service import Service
from app.models.user import User, UserRole
from app.models.working_hour import WorkingHour


async def _mk_user(session, name: str, email: str,
                   role: UserRole = UserRole.CLIENT) -> User:
    user = User(name=name, email=email, role=role, is_active=True)
    session.add(user)
    await session.flush()
    return user


def _factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


class TestNotificationSettingsApi:
    async def test_defaults_and_update(self, client, auth_headers):
        response = await client.get(
            "/api/v1/notifications/settings", headers=auth_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["preferred_channel"] == "auto"
        assert payload["digest_lead_minutes"] == 60
        assert payload["is_master"] is True
        assert set(payload["channels"]) == {"max", "vk", "email"}

        updated = await client.patch(
            "/api/v1/notifications/settings",
            json={
                "instant_enabled": False,
                "preferred_channel": "bell",
                "digest_lead_minutes": 120,
            },
            headers=auth_headers,
        )
        assert updated.status_code == 200, updated.text
        data = updated.json()
        assert data["instant_enabled"] is False
        assert data["preferred_channel"] == "bell"
        assert data["digest_lead_minutes"] == 120

    async def test_unknown_channel_rejected(self, client, auth_headers):
        response = await client.patch(
            "/api/v1/notifications/settings",
            json={"preferred_channel": "telegram"},
            headers=auth_headers,
        )
        assert response.status_code == 400


class TestExternalDispatch:
    async def test_auto_uses_last_login_channel(self, engine, monkeypatch):
        from app.config import settings
        from app.services import notification_dispatch as dispatch

        monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "test-token")

        sent = []

        class FakeMax:
            async def send_message(self, user_id, text, attachments=None):
                sent.append((user_id, text))
                return {}

        monkeypatch.setattr(dispatch, "MaxBotApi", FakeMax)

        factory = _factory(engine)
        async with factory() as db:
            user = await _mk_user(db, "Max Client", "max-dispatch@example.com")
            user.max_user_id = 12345
            user.last_login_provider = "max"
            db.add(Notification(
                recipient_id=user.id, text="Ваша запись подтверждена",
                audience="booking", link="appointments",
            ))
            await db.commit()
            notification_id = (await db.execute(
                select(Notification.id)
            )).scalar_one()

        result = await dispatch.run_notification_dispatch_once(factory)
        assert result == 1
        assert sent and sent[0][0] == 12345
        assert "http" in sent[0][1]

        async with factory() as db:
            note = await db.get(Notification, notification_id)
            assert note.external_channel == "max"
            assert note.external_sent_at is not None
            assert note.external_error is None

    async def test_instant_switch_suppresses_delivery(self, engine, monkeypatch):
        from app.config import settings
        from app.services import notification_dispatch as dispatch

        monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "test-token")

        class FakeMax:
            async def send_message(self, user_id, text, attachments=None):
                raise AssertionError("must not be called")

        monkeypatch.setattr(dispatch, "MaxBotApi", FakeMax)

        factory = _factory(engine)
        async with factory() as db:
            user = await _mk_user(db, "Quiet", "quiet-dispatch@example.com")
            user.max_user_id = 777
            user.last_login_provider = "max"
            db.add(NotificationPreference(user_id=user.id, instant_enabled=False))
            db.add(Notification(recipient_id=user.id, text="Тишина"))
            await db.commit()

        assert await dispatch.run_notification_dispatch_once(factory) == 0


class TestReminders:
    async def test_reminders_once_and_idempotent(self, engine, session, monkeypatch):
        from app.services import reminders

        fixed_now = datetime(2026, 5, 10, 12, 0)
        monkeypatch.setattr(reminders, "localnow_naive", lambda: fixed_now)

        client_user = await _mk_user(session, "Client", "reminder-c@example.com")
        master_user = await _mk_user(
            session, "Master", "reminder-m@example.com", UserRole.MASTER)
        client_profile = ClientProfile(user_id=client_user.id)
        master = MasterProfile(user_id=master_user.id)
        session.add_all([client_profile, master])
        await session.flush()
        service = Service(
            master_id=master.id, name="Стрижка",
            duration_minutes=60, price=1000, is_active=True,
        )
        session.add(service)
        await session.flush()
        appointment = Appointment(
            master_id=master.id, service_id=service.id,
            client_id=client_profile.id,
            appointment_date=fixed_now + timedelta(hours=3),
            status="confirmed",
        )
        session.add(appointment)
        await session.commit()

        factory = _factory(engine)
        assert await reminders.run_appointment_reminders_once(factory) == 1
        assert await reminders.run_appointment_reminders_once(factory) == 0

        async with factory() as db:
            rows = (await db.execute(
                select(Notification).where(
                    Notification.recipient_id == client_user.id)
            )).scalars().all()
            assert [n.kind for n in rows] == ["appointment_reminder_24h"]
            refreshed = await db.get(Appointment, appointment.id)
            assert refreshed.reminder_24h_sent_at is not None
            assert refreshed.reminder_2h_sent_at is None

    async def test_2h_only_when_inside_window(self, engine, session, monkeypatch):
        from app.services import reminders

        fixed_now = datetime(2026, 5, 10, 12, 0)
        monkeypatch.setattr(reminders, "localnow_naive", lambda: fixed_now)

        client_user = await _mk_user(session, "Soon", "soon-c@example.com")
        master_user = await _mk_user(
            session, "Soon Master", "soon-m@example.com", UserRole.MASTER)
        client_profile = ClientProfile(user_id=client_user.id)
        master = MasterProfile(user_id=master_user.id)
        session.add_all([client_profile, master])
        await session.flush()
        appointment = Appointment(
            master_id=master.id, client_id=client_profile.id,
            appointment_date=fixed_now + timedelta(hours=1),
            status="pending",
        )
        session.add(appointment)
        await session.commit()

        factory = _factory(engine)
        assert await reminders.run_appointment_reminders_once(factory) == 1

        async with factory() as db:
            rows = (await db.execute(
                select(Notification).where(
                    Notification.recipient_id == client_user.id)
            )).scalars().all()
            assert [n.kind for n in rows] == ["appointment_reminder_2h"]
            refreshed = await db.get(Appointment, appointment.id)
            assert refreshed.reminder_24h_sent_at is not None
            assert refreshed.reminder_2h_sent_at is not None


class TestMasterDigest:
    async def test_digest_once_per_day(self, engine, session, monkeypatch):
        from app.services import reminders

        fixed_now = datetime(2026, 5, 10, 9, 0)
        monkeypatch.setattr(reminders, "localnow_naive", lambda: fixed_now)

        master_user = await _mk_user(
            session, "Digest Master", "digest-m@example.com", UserRole.MASTER)
        client_user = await _mk_user(
            session, "Digest Client", "digest-c@example.com")
        master = MasterProfile(user_id=master_user.id)
        client_profile = ClientProfile(user_id=client_user.id)
        session.add_all([master, client_profile])
        await session.flush()
        session.add(WorkingHour(
            master_id=master.id, schedule_date=fixed_now.date(),
            start_time=time(10, 0), end_time=time(18, 0), is_active=True,
        ))
        session.add(Appointment(
            master_id=master.id, client_id=client_profile.id,
            appointment_date=datetime(2026, 5, 10, 11, 0),
            status="confirmed", price=1500,
        ))
        await session.commit()

        factory = _factory(engine)
        assert await reminders.run_master_digest_once(factory) == 1
        assert await reminders.run_master_digest_once(factory) == 0

        async with factory() as db:
            rows = (await db.execute(
                select(Notification).where(
                    Notification.recipient_id == master_user.id)
            )).scalars().all()
            assert [n.kind for n in rows] == ["master_digest"]
            assert "запись" in rows[0].text
            pref = (await db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == master_user.id)
            )).scalar_one()
            assert pref.last_digest_on == fixed_now.date()
