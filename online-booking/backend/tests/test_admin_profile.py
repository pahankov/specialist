"""GET /api/v1/admin/profile — own id/name/city for form defaults."""

from io import BytesIO

from PIL import Image


def _png_bytes(size=(8, 8), color=(200, 50, 50)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


class TestAdminProfile:
    async def test_master_profile_no_city(self, client, auth_headers):
        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"]
        assert body["city_id"] is None

    async def test_master_profile_sidebar_meta(self, client, auth_headers):
        """Sidebar needs profile_id (rating) + tariff badge fields."""
        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body["profile_id"], int)
        assert body["tariff"] == "trial"
        assert body["trial_ends_at"]
        assert body["auto_complete"] is False

    async def test_profile_exposes_auth_flags_and_contacts(
        self, client, session, auth_headers
    ):
        """1.79.0: bind buttons + password card need flags and contacts."""
        from sqlalchemy import select
        from app.models.user import User
        from app.services.contacts import attach_contact
        from app.utils.security import hash_password

        me = (await session.execute(
            select(User).where(User.role == "MASTER")
        )).scalar_one()
        me.hashed_password = hash_password("MasterPass123!")
        await attach_contact(session, me, "email", "master@example.com",
                             verified_via="code")
        await session.commit()

        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_password"] is True
        assert body["vk_bound"] is False
        assert body["yandex_bound"] is False
        assert body["max_bound"] is False
        emails = [c for c in body["contacts"] if c["contact_type"] == "email"]
        attached = [c for c in emails if c["value"] == "master@example.com"]
        assert len(attached) == 1
        assert attached[0]["verified_via"] == "code"
        # The fixture's own email keeps the primary slot.
        primaries = [c for c in emails if c["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["value"] != "master@example.com"

    async def test_master_profile_with_city(self, client, session, auth_headers):
        from sqlalchemy import select
        from app.models.city import City
        from app.models.country import Country
        from app.models.user import User

        country = Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7")
        session.add(country)
        await session.flush()
        city = City(country_id=country.id, name_ru="Казань", name_en="Kazan", slug="kazan")
        session.add(city)
        await session.flush()

        # auth master is the only MASTER user in this fresh DB
        me = (await session.execute(
            select(User).where(User.role == "MASTER")
        )).scalar_one()
        me.city_id = city.id
        await session.commit()

        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["city_id"] == city.id
        assert r.json()["city_name"] == "Казань"

    async def test_update_own_city(self, client, session, auth_headers):
        from sqlalchemy import select
        from app.models.city import City
        from app.models.country import Country

        country = Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7")
        session.add(country)
        await session.flush()
        city = City(country_id=country.id, name_ru="Сочи", name_en="Sochi", slug="sochi")
        session.add(city)
        await session.commit()

        r = await client.patch(
            "/api/v1/admin/profile", json={"city_id": city.id}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["city_id"] == city.id
        assert r.json()["city_name"] == "Сочи"

        again = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert again.json()["city_id"] == city.id

    async def test_update_unknown_city_404(self, client, auth_headers):
        r = await client.patch(
            "/api/v1/admin/profile", json={"city_id": 999999}, headers=auth_headers
        )
        assert r.status_code == 404

    async def test_update_personal_data(self, client, session, auth_headers):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.user import User

        r = await client.patch(
            "/api/v1/admin/profile",
            json={
                "name": "Анна",
                "last_name": "Смирнова",
                "telegram_username": "anna_pro",
                "description": "Опытный мастер",
                "experience_years": 7,
                "cabinet_address": "г. Казань, ул. Баумана, 10",
                "certificates": [
                    {"name": "Шугаринг PRO"},
                    {"name": "Стерильность", "url": "/static/avatars/x.png"},
                ],
            },
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "Анна Смирнова"
        assert body["last_name"] == "Смирнова"
        assert body["cabinet_address"] == "г. Казань, ул. Баумана, 10"
        assert body["experience_years"] == 7
        assert [c["name"] for c in body["certificates"]] == ["Шугаринг PRO", "Стерильность"]

        me = (await session.execute(
            select(User).where(User.role == "MASTER")
        )).scalar_one()
        assert me.name == "Анна Смирнова"

    async def test_update_last_name_only(self, client, auth_headers):
        await client.patch(
            "/api/v1/admin/profile",
            json={"name": "Ольга", "last_name": "Ким"},
            headers=auth_headers,
        )
        r = await client.patch(
            "/api/v1/admin/profile", json={"last_name": "Пак"}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Ольга Пак"
        assert r.json()["last_name"] == "Пак"


class TestAvatarUpload:
    async def test_upload_avatar(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("ava.png", _png_bytes(), "image/png")},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        url = r.json()["avatar_url"]
        assert url.startswith("/static/avatars/user_")

        me = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert me.json()["avatar_url"] == url

        # Cleanup the uploaded file (tests must not litter the repo).
        import os as _os

        _os.remove(_os.path.join(
            "app", "static", "avatars", _os.path.basename(url)))

    async def test_upload_rejects_non_image(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("evil.txt", b"hello", "text/plain")},
            headers=auth_headers,
        )
        assert r.status_code == 400

    async def test_upload_rejects_spoofed_image(self, client, auth_headers):
        """An image MIME type must not bypass actual decoding/re-encoding."""
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("fake.png", b"<svg>not an image</svg>", "image/png")},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "распознать" in r.json()["detail"]

    async def test_upload_rejects_oversize(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("big.png", b"0" * (16 * 1024 * 1024), "image/png")},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "15 МБ" in r.json()["detail"]

    async def test_upload_accepts_generic_phone_mime(self, client, auth_headers):
        """Some Android pickers send application/octet-stream; sniff bytes."""
        img = Image.new("RGB", (120, 80), (20, 120, 80))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("camera.bin", buf.getvalue(), "application/octet-stream")},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        import os as _os

        _os.remove(_os.path.join(
            "app", "static", "avatars", _os.path.basename(r.json()["avatar_url"])))

    async def test_upload_iphone_heic(self, client, auth_headers):
        from pillow_heif import register_heif_opener

        register_heif_opener()
        img = Image.new("RGB", (1600, 1200), (210, 90, 120))
        buf = BytesIO()
        img.save(buf, format="HEIF", quality=90)
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("iphone.heic", buf.getvalue(), "image/heic")},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        url = r.json()["avatar_url"]
        assert url.endswith(".jpg")

        import os as _os

        path = _os.path.join("app", "static", "avatars", _os.path.basename(url))
        try:
            with Image.open(path) as saved:
                assert saved.format == "JPEG"
                assert max(saved.size) <= 1024
        finally:
            _os.remove(path)

    async def test_exif_orientation_is_applied(self, client, auth_headers):
        """Phone portrait photos must not stay sideways after re-encoding."""
        img = Image.new("RGB", (40, 80), (10, 10, 10))
        exif = Image.Exif()
        exif[274] = 6  # Orientation: rotate 90° clockwise
        buf = BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("portrait.jpg", buf.getvalue(), "image/jpeg")},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        import os as _os

        path = _os.path.join(
            "app", "static", "avatars", _os.path.basename(r.json()["avatar_url"]))
        try:
            with Image.open(path) as saved:
                assert saved.size == (80, 40)
        finally:
            _os.remove(path)

    async def test_upload_downscales_big_photo(self, client, auth_headers):
        from io import BytesIO
        from PIL import Image
        import os as _os

        img = Image.new("RGB", (2000, 1500), (200, 50, 50))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=95)
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("big.jpg", buf.getvalue(), "image/jpeg")},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        url = r.json()["avatar_url"]
        path = _os.path.join("app", "static", "avatars",
                             _os.path.basename(url))
        try:
            with Image.open(path) as saved:
                assert max(saved.size) <= 1024, saved.size
        finally:
            _os.remove(path)


class TestAvatarPreset:
    async def test_set_preset_clears_upload(self, client, auth_headers):
        up = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("ava.png", _png_bytes(), "image/png")},
            headers=auth_headers,
        )
        assert up.status_code == 200, up.text
        old_url = up.json()["avatar_url"]

        r = await client.patch(
            "/api/v1/admin/profile", json={"avatar_preset": "🐱"},
            headers=auth_headers)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["avatar_preset"] == "🐱"
        assert me["avatar_url"] is None

        # Old uploaded file is removed (mutually exclusive).
        import os as _os
        assert not _os.path.exists(_os.path.join(
            "app", "static", "avatars", _os.path.basename(old_url)))

    async def test_reject_unknown_preset(self, client, auth_headers):
        r = await client.patch(
            "/api/v1/admin/profile", json={"avatar_preset": "🚀"},
            headers=auth_headers)
        assert r.status_code == 400

    async def test_clear_preset(self, client, auth_headers):
        await client.patch(
            "/api/v1/admin/profile", json={"avatar_preset": "🐶"},
            headers=auth_headers)
        r = await client.patch(
            "/api/v1/admin/profile", json={"avatar_preset": None},
            headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["avatar_preset"] is None

    async def test_preset_in_public_masters(self, client, auth_headers):
        await client.patch(
            "/api/v1/admin/profile", json={"avatar_preset": "🦅"},
            headers=auth_headers)
        r = await client.get("/api/v1/masters/")
        assert r.status_code == 200, r.text
        assert any(m.get("avatar_preset") == "🦅" for m in r.json())

    async def test_cert_upload_keeps_avatar(self, client, auth_headers):
        """kind=cert must not touch avatar_url (shared endpoint used to
        overwrite it and delete the previous file — saved certs 404'd)."""
        import os as _os

        up = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("ava.png", _png_bytes(), "image/png")},
            headers=auth_headers,
        )
        assert up.status_code == 200, up.text
        avatar_url = up.json()["avatar_url"]

        cert = await client.post(
            "/api/v1/admin/profile/avatar?kind=cert",
            files={"file": ("cert.png", _png_bytes(color=(20, 80, 160)), "image/png")},
            headers=auth_headers,
        )
        assert cert.status_code == 200, cert.text
        cert_url = cert.json()["avatar_url"]
        assert cert_url != avatar_url

        me = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert me.json()["avatar_url"] == avatar_url
        # Both files survive on disk.
        for url in (avatar_url, cert_url):
            assert _os.path.exists(_os.path.join(
                "app", "static", "avatars", _os.path.basename(url)))
            _os.remove(_os.path.join(
                "app", "static", "avatars", _os.path.basename(url)))

    async def test_upload_rejects_bad_kind(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/profile/avatar?kind=passport",
            files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 10, "image/png")},
            headers=auth_headers,
        )
        assert r.status_code in (400, 422)

    async def test_cert_url_scheme_validated(self, client, auth_headers):
        r = await client.patch(
            "/api/v1/admin/profile",
            json={"certificates": [
                {"name": "X", "url": "javascript:alert(1)"},
            ]},
            headers=auth_headers,
        )
        assert r.status_code == 422

        ok = await client.patch(
            "/api/v1/admin/profile",
            json={"certificates": [
                {"name": "Y", "url": "/static/avatars/a.png"},
            ]},
            headers=auth_headers,
        )
        assert ok.status_code == 200, ok.text


class TestAdminOwnContacts:
    """1.79.4: manual add/remove/promote of own contacts in the panel profile.

    Self-typed values land UNVERIFIED (status «не подтверждён») — same model
    as the client cabinet, exposed so the super can keep extra phones/emails.
    """

    async def test_add_phone_lands_unverified(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/profile/contacts",
            json={"contact_type": "phone", "value": "+7 999 222-33-44"},
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["value"] == "+7 (999) 222-33-44"  # normalized
        assert body["is_verified"] is False
        assert body["verified_via"] is None
        assert body["is_primary"] is False

    async def test_added_contact_visible_in_profile(self, client, auth_headers):
        await client.post(
            "/api/v1/admin/profile/contacts",
            json={"contact_type": "email", "value": "Extra@Example.com"},
            headers=auth_headers,
        )
        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        emails = [c for c in r.json()["contacts"] if c["contact_type"] == "email"]
        assert any(
            c["value"] == "extra@example.com" and not c["is_verified"]
            for c in emails
        )

    async def test_add_rejects_foreign_contact(self, client, session, auth_headers):
        from app.models.user import User, UserRole
        from app.services.contacts import attach_contact

        other = User(name="Other", role=UserRole.CLIENT, is_active=True)
        session.add(other)
        await session.flush()
        await attach_contact(session, other, "phone", "+7 (999) 111-22-33")
        await session.commit()

        r = await client.post(
            "/api/v1/admin/profile/contacts",
            json={"contact_type": "phone", "value": "+7 999 111-22-33"},
            headers=auth_headers,
        )
        assert r.status_code == 409

    async def test_add_rejects_bad_email(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/profile/contacts",
            json={"contact_type": "email", "value": "not-an-email"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_promote_and_remove(self, client, auth_headers):
        added = await client.post(
            "/api/v1/admin/profile/contacts",
            json={"contact_type": "phone", "value": "+7 999 222-33-44"},
            headers=auth_headers,
        )
        cid = added.json()["id"]

        prim = await client.post(
            f"/api/v1/admin/profile/contacts/{cid}/primary",
            headers=auth_headers,
        )
        assert prim.status_code == 200, prim.text
        assert prim.json()["is_primary"] is True

        rm = await client.delete(
            f"/api/v1/admin/profile/contacts/{cid}", headers=auth_headers
        )
        assert rm.status_code == 200, rm.text
        assert rm.json() == {"ok": True}

    async def test_cannot_remove_last_contact(self, client, auth_headers):
        """A password account keeps at least one contact (login identifier)."""
        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        contacts = r.json()["contacts"]
        assert len(contacts) >= 2  # phone + email from registration

        for c in contacts[:-1]:
            rm = await client.delete(
                f"/api/v1/admin/profile/contacts/{c['id']}", headers=auth_headers
            )
            assert rm.status_code == 200, rm.text

        last = contacts[-1]
        blocked = await client.delete(
            f"/api/v1/admin/profile/contacts/{last['id']}", headers=auth_headers
        )
        assert blocked.status_code == 400
        assert "последний" in blocked.json()["detail"].lower()
