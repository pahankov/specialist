"""Sidebar support requests reach the superadmin bell."""
import pytest
from sqlalchemy import select


async def _mk_user(session, name, email, role_value):
    from app.models.user import User, UserRole

    user = User(
        name=name,
        email=email,
        role=UserRole(role_value),
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


def _headers_for(user):
    from app.modules.auth.token import create_access_token

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "is_admin": user.role.value == "ADMIN",
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestSupportRequests:
    async def test_master_request_creates_superadmin_notification(
        self, client, session, super_admin_user, super_admin_headers
    ):
        from app.models.notification import Notification

        master = await _mk_user(session, "Master Support", "support-master@example.com", "MASTER")
        await session.commit()

        response = await client.post(
            "/api/v1/support/request",
            json={"message": "Не получается изменить расписание", "page": "/admin/schedule"},
            headers=_headers_for(master),
        )
        assert response.status_code == 200, response.text
        assert response.json()["delivered"] == 1

        rows = list((await session.execute(
            select(Notification).where(
                Notification.recipient_id == super_admin_user.id,
                Notification.kind == "support",
            )
        )).scalars().all())
        assert len(rows) == 1
        note = rows[0]
        assert note.sender_id == master.id
        assert note.audience == "support"
        assert note.link == "support"
        assert "Master Support" in note.text
        assert "мастер" in note.text
        assert "/admin/schedule" in note.text
        assert "Не получается изменить расписание" in note.text

        badge = await client.get(
            "/api/v1/admin/notifications/unread-count",
            headers=super_admin_headers,
        )
        assert badge.status_code == 200, badge.text
        assert badge.json()["unread"] >= 1

    async def test_client_request_is_accepted(self, client, session, super_admin_user):
        from app.models.notification import Notification

        client_user = await _mk_user(
            session, "Client Support", "support-client@example.com", "CLIENT"
        )
        await session.commit()

        response = await client.post(
            "/api/v1/support/request",
            json={"message": "Подскажите, как перенести запись"},
            headers=_headers_for(client_user),
        )
        assert response.status_code == 200, response.text

        count = len(list((await session.execute(
            select(Notification).where(
                Notification.recipient_id == super_admin_user.id,
                Notification.kind == "support",
            )
        )).scalars().all()))
        assert count == 1

    async def test_short_message_is_rejected(self, client, session, super_admin_user):
        client_user = await _mk_user(
            session, "Short", "support-short@example.com", "CLIENT"
        )
        await session.commit()

        response = await client.post(
            "/api/v1/support/request",
            json={"message": "   коротко   "},
            headers=_headers_for(client_user),
        )
        assert response.status_code == 400, response.text

    async def test_anonymous_request_is_rejected(self, client):
        response = await client.post(
            "/api/v1/support/request",
            json={"message": "Нужна помощь с расписанием"},
        )
        assert response.status_code == 401, response.text
