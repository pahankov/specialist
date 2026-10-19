"""Tests for «Подтвердить почту» (1.79.3): emailed confirm codes for own
email contacts — cabinet (/client/contacts) and profile (/admin/profile)."""
import pytest

from app.services import mailer


@pytest.fixture
def sent_confirm_codes(monkeypatch):
    """Capture codes "sent" by the mailer instead of hitting SMTP."""
    captured = {}

    async def fake_confirm(to, code):
        captured[to] = code
        return True

    monkeypatch.setattr(mailer, "send_email_confirm_code", fake_confirm)
    return captured


@pytest.fixture
async def cabinet_user(session):
    """Client account + auth headers (client cabinet endpoints)."""
    from app.models.user import User, UserRole
    from app.modules.auth.token import create_access_token

    user = User(
        name="Confirm Client", email="confirm-client@example.com",
        phone="+7 (999) 000-55-55", hashed_password=None,
        role=UserRole.CLIENT, is_active=True, is_verified=True,
    )
    session.add(user)
    await session.flush()
    await session.commit()
    token = create_access_token({
        "sub": str(user.id), "role": "CLIENT", "name": user.name,
        "is_admin": False,
    })
    return user.id, {"Authorization": f"Bearer {token}"}


class TestCabinetContactVerify:
    async def test_email_roundtrip(
        self, client, cabinet_user, sent_confirm_codes
    ):
        _, headers = cabinet_user
        add = await client.post(
            "/api/v1/client/contacts", headers=headers,
            json={"contact_type": "email", "value": "new@example.com"},
        )
        assert add.status_code == 201, add.text
        contact_id = add.json()["id"]
        assert add.json()["is_verified"] is False

        send = await client.post(
            f"/api/v1/client/contacts/{contact_id}/send-code", headers=headers)
        assert send.status_code == 200, send.text
        assert "new@example.com" in sent_confirm_codes

        wrong = await client.post(
            f"/api/v1/client/contacts/{contact_id}/verify-code",
            headers=headers, json={"code": "000000"})
        assert wrong.status_code == 400

        ok = await client.post(
            f"/api/v1/client/contacts/{contact_id}/verify-code",
            headers=headers,
            json={"code": sent_confirm_codes["new@example.com"]})
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["is_verified"] is True
        assert body["verified_via"] == "code"

    async def test_phone_contact_rejected(self, client, cabinet_user):
        """Codes are email-only: phones confirm via MAX/social logins."""
        _, headers = cabinet_user
        add = await client.post(
            "/api/v1/client/contacts", headers=headers,
            json={"contact_type": "phone", "value": "+7 (999) 000-22-33"},
        )
        assert add.status_code == 201, add.text
        resp = await client.post(
            f"/api/v1/client/contacts/{add.json()['id']}/send-code",
            headers=headers)
        assert resp.status_code == 400

    async def test_foreign_contact_404(self, client, cabinet_user):
        _, headers = cabinet_user
        resp = await client.post(
            "/api/v1/client/contacts/9999/send-code", headers=headers)
        assert resp.status_code == 404


class TestAdminContactVerify:
    async def test_email_roundtrip(
        self, client, session, super_admin_user, super_admin_headers,
        sent_confirm_codes
    ):
        """The superadmin profile («Как подтвердить почту?») confirms too."""
        from app.services.contacts import attach_contact

        await attach_contact(
            session, super_admin_user, "email", "super2@example.com")
        await session.commit()

        me = await client.get(
            "/api/v1/admin/profile", headers=super_admin_headers)
        contact = [c for c in me.json()["contacts"]
                   if c["value"] == "super2@example.com"][0]
        assert contact["is_verified"] is False

        send = await client.post(
            f"/api/v1/admin/profile/contacts/{contact['id']}/send-code",
            headers=super_admin_headers)
        assert send.status_code == 200, send.text
        assert "super2@example.com" in sent_confirm_codes

        ok = await client.post(
            f"/api/v1/admin/profile/contacts/{contact['id']}/verify-code",
            headers=super_admin_headers,
            json={"code": sent_confirm_codes["super2@example.com"]})
        assert ok.status_code == 200, ok.text
        assert ok.json()["is_verified"] is True
        assert ok.json()["verified_via"] == "code"

    async def test_wrong_code_400(
        self, client, session, super_admin_user, super_admin_headers,
        sent_confirm_codes
    ):
        from app.services.contacts import attach_contact

        await attach_contact(
            session, super_admin_user, "email", "super3@example.com")
        await session.commit()

        me = await client.get(
            "/api/v1/admin/profile", headers=super_admin_headers)
        contact = [c for c in me.json()["contacts"]
                   if c["value"] == "super3@example.com"][0]

        await client.post(
            f"/api/v1/admin/profile/contacts/{contact['id']}/send-code",
            headers=super_admin_headers)
        resp = await client.post(
            f"/api/v1/admin/profile/contacts/{contact['id']}/verify-code",
            headers=super_admin_headers, json={"code": "999999"})
        assert resp.status_code == 400
