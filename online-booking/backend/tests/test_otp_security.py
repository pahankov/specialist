"""OTP brute-force protection: attempt counter, burn and code rotation."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.models.otp_code import OtpCode
from app.modules.auth.service import send_otp, verify_otp
from app.utils.security import hash_otp_code

PHONE = "+79990000421"


async def _store_code(session, code: str = "123456") -> OtpCode:
    otp = OtpCode(
        phone=PHONE,
        code_hash=hash_otp_code(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        is_used=False,
        attempts=0,
        channel="sms",
    )
    session.add(otp)
    await session.commit()
    await session.refresh(otp)
    return otp


class TestOtpAttempts:
    async def test_wrong_codes_burn_the_otp(self, session):
        otp = await _store_code(session)
        max_attempts = max(1, settings.SMS_MAX_ATTEMPTS)

        for attempt in range(1, max_attempts):
            with pytest.raises(HTTPException) as exc:
                await verify_otp(PHONE, "000000", session)
            assert exc.value.status_code == 400
            await session.refresh(otp)
            assert otp.attempts == attempt
            assert otp.is_used is False

        with pytest.raises(HTTPException) as exc:
            await verify_otp(PHONE, "000000", session)
        assert exc.value.status_code == 429

        await session.refresh(otp)
        assert otp.attempts == max_attempts
        assert otp.is_used is True

        # Even the correct code must not work after the burn.
        with pytest.raises(HTTPException) as exc:
            await verify_otp(PHONE, "123456", session)
        assert exc.value.status_code == 400

    async def test_new_sms_code_invalidates_previous_unused_code(
        self, session, monkeypatch,
    ):
        class _FakeSender:
            async def send(self, phone: str, code: str) -> bool:
                return True

        monkeypatch.setattr(
            "app.services.sms.provider.get_sms_provider",
            lambda: _FakeSender(),
        )

        await send_otp(PHONE, session)
        await send_otp(PHONE, session)

        rows = (await session.execute(
            select(OtpCode).where(OtpCode.phone == PHONE)
        )).scalars().all()
        assert len(rows) == 2
        assert sum(1 for row in rows if not row.is_used) == 1
