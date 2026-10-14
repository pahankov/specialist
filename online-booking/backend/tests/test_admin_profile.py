"""GET /api/v1/admin/profile — own id/name/city for form defaults."""


class TestAdminProfile:
    async def test_master_profile_no_city(self, client, auth_headers):
        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"]
        assert body["city_id"] is None

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
            files={"file": ("ava.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")},
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

    async def test_upload_rejects_oversize(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/profile/avatar",
            files={"file": ("big.png", b"0" * (6 * 1024 * 1024), "image/png")},
            headers=auth_headers,
        )
        assert r.status_code == 400

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
            files={"file": ("ava.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")},
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
            files={"file": ("ava.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")},
            headers=auth_headers,
        )
        assert up.status_code == 200, up.text
        avatar_url = up.json()["avatar_url"]

        cert = await client.post(
            "/api/v1/admin/profile/avatar?kind=cert",
            files={"file": ("cert.png", b"\x89PNG\r\n\x1a\n" + b"1" * 100, "image/png")},
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
