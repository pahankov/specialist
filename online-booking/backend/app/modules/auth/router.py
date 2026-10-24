"""Authentication API endpoints — register, login, OTP, refresh, logout."""
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Response, Request, File, Query, UploadFile
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, field_validator
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from datetime import datetime, timezone as dt_timezone

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.city import City
from app.models.refresh_token import RefreshToken
from app.models.country import Country
from app.schemas.user import UserCreate, UserLoginByEmail
from app.schemas.otp import SendOtpRequest, VerifyOtpRequest, OtpResponse
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    PhoneStatusRequest,
    PhoneStatusResponse,
    ResetPasswordRequest,
    TokenResponse,
    TokenRefreshResponse,
    TokenRefreshRequest,
    UnifiedLoginRequest,
    UnifiedRegisterRequest,
)
from app.config import settings
from app.logging_config import get_logger
from app.services.audit import log_action
from app.services.master_landing import master_landing_preference
from app.services.master_profile_view import master_profile_snapshot
from app.services.names import set_names
from app.services.notifications import send_master_activated_bell
from app.modules.auth import service
from app.modules.auth.token import create_access_token, create_refresh_token_payload
from app.modules.admin.profile import (
    AVATAR_DIR,
    AVATAR_PRESETS,
    AVATAR_URL_PREFIX,
    IMAGE_SIZE_ERROR,
    IMAGE_TYPE_ERROR,
    MAX_AVATAR_BYTES,
    is_image_content_type,
)
from app.dependencies.auth import get_current_user, require_client
from app.middleware.rate_limit import limiter
from app.utils.cookies_http import set_auth_cookies


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token_value: str
) -> None:
    """Backward-compatible alias — canonical home is app.utils.cookies_http."""
    set_auth_cookies(response, access_token, refresh_token_value)

logger = get_logger(__name__)

router = APIRouter()

security = HTTPBearer(auto_error=False)


# ─── Registration ─────────────────────────────────────────────────────

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register_master(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new master. Requires city_id."""
    logger.info("Register master request: email=%s, name=%s", user_data.email, user_data.name)
    if user_data.role != UserRole.MASTER:
        logger.warning("Register failed: role=%s, expected MASTER", user_data.role)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Только мастера могут зарегистрироваться через этот endpoint"
        )

    new_user = await service.register_master(user_data, db)
    logger.info("Master registered successfully: id=%s, email=%s", new_user.id, new_user.email)

    # Load master_profile to get its ID
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(MasterProfile).where(MasterProfile.user_id == new_user.id))
    master_profile = result.scalar_one_or_none()

    return {
        "id": master_profile.id if master_profile else new_user.id,
        "name": new_user.name,
        "email": new_user.email,
        "phone": new_user.phone,
        "role": new_user.role.value,
        "city_id": new_user.city_id,
        "is_active": new_user.is_active,
        "is_verified": new_user.is_verified,
        "telegram_username": master_profile.telegram_username if master_profile else None,
        "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
        "updated_at": new_user.updated_at.isoformat() if new_user.updated_at else None,
    }


# ─── Login ────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, response: Response, req: UserLoginByEmail, db: AsyncSession = Depends(get_db)):
    """Email+password login for client/admin — masters are social-only (403).

    Returns the access token in the body and the refresh token in an
    httpOnly cookie.
    """
    logger.info("Login attempt by email: %s", req.email)
    try:
        access_token, user = await service.login_master(req.email, req.password, db)
        logger.info("Login successful: user_id=%s, email=%s", user.id, user.email)

        # Get the most recent refresh token for this user
        result = await db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.is_revoked == False
            )
            .order_by(RefreshToken.id.desc())
            .limit(1)
        )
        stored = result.scalar_one_or_none()
        cookie_token = stored.token if stored else None

        _set_auth_cookies(response, access_token, cookie_token)
        await log_action(
            db, user.id, "login", "auth", user.id,
            f"Вход: {user.email} ({user.role.value})", level="info",
        )
        await db.commit()
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Login failed (HTTP): email=%s", req.email)
        raise
    except Exception as e:
        logger.error("Login failed (unexpected): email=%s, error=%s", req.email, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка авторизации")


# ─── OTP Authentication ──────────────────────────────────────────────

@router.post("/send-otp", response_model=OtpResponse)
@limiter.limit("10/minute")
async def send_otp(request: Request, req: SendOtpRequest, db: AsyncSession = Depends(get_db)):
    """Send OTP code to phone number."""
    logger.info("Send OTP request: phone=%s", req.phone)
    try:
        await service.send_otp(req.phone, db)
        logger.info("OTP sent successfully: phone=%s", req.phone)
        return {"message": "Код отправлен"}
    except Exception as e:
        logger.error("Failed to send OTP to %s: %s", req.phone, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Не удалось отправить код")


@router.post("/verify-otp", response_model=TokenResponse)
@limiter.limit("10/minute")
async def verify_otp(request: Request, req: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    """Verify OTP code and login/create user."""
    logger.info("Verify OTP request: phone=%s", req.phone)
    try:
        access_token, user = await service.verify_otp(req.phone, req.code, db)
        logger.info("OTP verified: user_id=%s, phone=%s", user.id, user.phone)
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("OTP verification failed: phone=%s", req.phone)
        raise
    except Exception as e:
        logger.error("OTP verification failed (unexpected): phone=%s, error=%s", req.phone, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка верификации")


# ─── Token Refresh ────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """Refresh access token with rotation."""
    cookie_token = request.cookies.get("refresh_token")
    if not cookie_token:
        logger.warning("Token refresh: missing refresh_token cookie")
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = jwt.decode(cookie_token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            logger.warning("Token refresh: invalid token type: %s", payload.get("type"))
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload["sub"])
        logger.debug("Token refresh: decoded JWT for user_id=%s", user_id)
    except jwt.PyJWTError as e:
        logger.warning("Token refresh: JWT decode failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == cookie_token,
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        )
    )
    stored_token = result.scalar_one_or_none()

    if not stored_token:
        # Rotation race (two tabs refreshing at once): the loser presents
        # the just-revoked token. Grace window — if it was revoked moments
        # ago by a legit rotation AND a live token exists, rotate from the
        # live one instead of logging the user out.
        revoked = (await db.execute(
            select(RefreshToken).where(
                RefreshToken.token == cookie_token,
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == True,
            )
        )).scalar_one_or_none()
        now_utc = datetime.now(dt_timezone.utc)
        if revoked is not None:
            revoked_at = revoked.revoked_at
            if revoked_at is not None and revoked_at.tzinfo is None:
                revoked_at = revoked_at.replace(tzinfo=dt_timezone.utc)
            live = (await db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False,
                ).order_by(RefreshToken.id.desc())
            )).scalars().first()
            if (live is not None and revoked_at is not None
                    and (now_utc - revoked_at).total_seconds() <= 60):
                logger.info("Token refresh: rotation race absorbed for user_id=%s", user_id)
                stored_token = live
        if not stored_token:
            logger.warning("Token refresh: token not found for user_id=%s", user_id)
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Handle timezone-aware vs naive datetime comparison (SQLite stores naive datetimes)
    expires_at = stored_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dt_timezone.utc)
    if expires_at < datetime.now(dt_timezone.utc):
        logger.warning("Token refresh: token not found or expired for user_id=%s", user_id)
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning("Token refresh: user not found: user_id=%s", user_id)
        raise HTTPException(status_code=401, detail="User not found")

    stored_token.is_revoked = True
    stored_token.revoked_at = datetime.now(dt_timezone.utc)

    new_access = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "is_admin": user.role == UserRole.ADMIN,
        "prefer_master": await master_landing_preference(db, user),
    })
    new_refresh_value, new_expires = create_refresh_token_payload(user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=new_refresh_value, expires_at=new_expires))

    # Housekeeping: drop long-dead rotations (one row per refresh otherwise).
    from datetime import timedelta as _td
    await db.execute(
        RefreshToken.__table__.delete().where(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked == True,
            RefreshToken.revoked_at < datetime.now(dt_timezone.utc) - _td(days=30),
        )
    )

    await db.commit()

    response = Response(
        content=f'{{"access_token":"{new_access}","token_type":"bearer"}}'
    )
    _set_auth_cookies(response, new_access, new_refresh_value)
    logger.info("Token refreshed: user_id=%s, old_token revoked, new token issued", user_id)
    return response


# ─── Logout ───────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Logout — revoke all refresh tokens for current user."""
    cookie_token = request.cookies.get("refresh_token")
    if cookie_token:
        try:
            payload = jwt.decode(cookie_token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = int(payload["sub"])
            logger.info("Logout: revoking all refresh tokens for user_id=%s", user_id)
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)
                .values(is_revoked=True, revoked_at=datetime.now(dt_timezone.utc))
            )
            await log_action(
                db, user_id, "logout", "auth", user_id, "Выход", level="info",
            )
            await db.commit()
        except jwt.PyJWTError:
            logger.debug("Logout: invalid JWT in cookie, skipping token revocation")
            pass

    response = Response(content='{"detail":"Logged out"}')
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="access_token", path="/")
    return response


# ─── Unified Login ───────────────────────────────────────────────────

@router.post("/login-unified", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login_unified(
    request: Request,
    response: Response,
    req: UnifiedLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login with email OR phone + password. Works for both clients and masters.

    Unknown contacts (after the 152-FZ consent retry) create a CLIENT cabinet
    on the fly — the unified entry has no separate «нет аккаунта» form.
    """
    logger.info("Unified login attempt: identifier=%s", req.identifier)
    try:
        access_token, user, created = await service.login_unified(
            req.identifier, req.password, db, consent=req.consent)
        logger.info("Unified login successful: user_id=%s, role=%s", user.id, user.role.value)

        # Get the most recent refresh token for this user
        result = await db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.is_revoked == False
            )
            .order_by(RefreshToken.id.desc())
            .limit(1)
        )
        stored = result.scalar_one_or_none()
        cookie_token = stored.token if stored else None

        _set_auth_cookies(response, access_token, cookie_token)
        await log_action(
            db, user.id,
            "register" if created else "login", "auth", user.id,
            (
                f"Регистрация: {user.email or user.phone} ({user.role.value})"
                if created
                else f"Вход: {user.email or user.phone} ({user.role.value})"
            ),
            level="info",
        )
        await db.commit()
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Unified login failed: identifier=%s", req.identifier)
        raise
    except Exception as e:
        logger.error("Unified login failed (unexpected): identifier=%s, error=%s", req.identifier, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка авторизации")


@router.post("/phone/status", response_model=PhoneStatusResponse)
@limiter.limit("10/minute")
async def phone_status(
    request: Request,
    req: PhoneStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """Unified entry («Единый вход») step 1: password / social / new hint.

    The single entry screen posts the typed phone here and then shows the
    matching step: password field for password accounts, a «войдите через
    VK/Яндекс/MAX» hint for social-only accounts, phone+password signup
    for new numbers.
    """
    return await service.phone_status(req.phone, db)


# ─── Unified Registration ────────────────────────────────────────────

@router.post("/register-unified", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register_unified(
    request: Request,
    response: Response,
    req: UnifiedRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Quick registration: phone + password, everyone a CLIENT.

    Logs the user in immediately: returns access_token + sets auth cookies,
    so the client lands straight in its cabinet (no extra login step).

    For the 2-step consent flow (1.80.0), the frontend sends a ``challenge``
    token (from /phone/status) — the phone is extracted from the challenge
    and ``phone`` in the body is ignored.
    """
    # Resolve the phone: from challenge (2-step) or from body (legacy).
    phone = req.phone
    if req.challenge:
        payload = service._decode_challenge_token(req.challenge)
        phone = payload["phone"]
        logger.info("Register via challenge: phone=%s", phone)
    else:
        logger.info("Quick register: phone=%s", phone)
    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Укажите телефон или пройдите шаг проверки номера.",
        )
    try:
        new_user = await service.register_unified(
            phone=phone,
            password=req.password,
            consent=req.consent,
            db=db,
        )
        logger.info(
            "Register successful: user_id=%s, role=%s",
            new_user.id, new_user.role.value
        )

        access_token = create_access_token({
            "sub": str(new_user.id),
            "role": new_user.role.value,
            "name": new_user.name,
            "last_name": new_user.last_name,
            "is_admin": new_user.role == UserRole.ADMIN,
        })
        refresh_value, expires_at = create_refresh_token_payload(
            new_user.id, new_user.email or "")
        db.add(RefreshToken(user_id=new_user.id, token=refresh_value,
                            expires_at=expires_at))
        _set_auth_cookies(response, access_token, refresh_value)
        await log_action(
            db, new_user.id, "register", "auth", new_user.id,
            f"Регистрация: {new_user.phone} ({new_user.role.value})",
            level="info",
        )
        await db.commit()
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Quick register failed: phone=%s", phone)
        raise
    except Exception as e:
        logger.error("Quick register failed (unexpected): phone=%s, error=%s", phone, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка регистрации")


# ─── Become master (client fills the master profile, self-activates) ──

class BecomeMasterCertificate(BaseModel):
    """One diploma/certificate photo (optional url)."""
    name: str = Field(min_length=1, max_length=200)
    url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("url")
    @classmethod
    def _safe_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        if not (s.startswith("/") or s.startswith("http://")
                or s.startswith("https://")):
            raise ValueError("URL сертификата: только /static/... или http(s)")
        return s


class MasterDraftRequest(BaseModel):
    """Master profile draft / activation payload (1.83.0).

    The client reuses the master profile form. Saving an incomplete draft
    is allowed; activation additionally requires both names, a cabinet
    address, a phone, a VERIFIED email and a bound social account.
    """
    name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    cabinet_address: Optional[str] = Field(default=None, max_length=500)
    city_id: Optional[int] = None
    description: Optional[str] = None
    experience_years: Optional[int] = Field(default=None, ge=0, le=80)
    telegram_username: Optional[str] = Field(default=None, max_length=100)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    avatar_preset: Optional[str] = Field(default=None, max_length=12)
    certificates: Optional[List[BecomeMasterCertificate]] = Field(
        default=None, max_length=20)
    auto_confirm: Optional[bool] = None
    auto_complete: Optional[bool] = None
    prefer_master_cabinet: Optional[bool] = None
    # Explicit acceptance of the separate paid-master annex. Required at
    # activation; draft saves may omit it.
    accept_master_terms: Optional[bool] = None

    @field_validator("avatar_url")
    @classmethod
    def _safe_avatar(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        s = v.strip()
        if not (s.startswith("/") or s.startswith("http://")
                or s.startswith("https://")):
            raise ValueError("Некорректный адрес фото")
        return s


def _draft_status(user: User, mp: Optional[MasterProfile]) -> str:
    if user.role == UserRole.MASTER:
        return "active"
    return "draft" if mp is not None else "none"


async def _get_draft(db: AsyncSession, user: User) -> Optional[MasterProfile]:
    return (await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == user.id)
    )).scalar_one_or_none()


async def _apply_draft(
    db: AsyncSession,
    user: User,
    mp: Optional[MasterProfile],
    data: MasterDraftRequest,
) -> MasterProfile:
    """Apply the form to a new or existing inactive MasterProfile."""
    if mp is None:
        mp = MasterProfile(
            user_id=user.id,
            status="inactive",
            is_active=False,
            prefer_master_cabinet=True,
        )
        db.add(mp)
        await db.flush()

    # Names are optional in draft mode so a half-filled profile can be saved.
    if data.name is not None or data.last_name is not None:
        first = (data.name if data.name is not None
                 else (user.name or "").split(" ")[0]).strip()
        last = (data.last_name if data.last_name is not None
                else (user.last_name or "")).strip()
        if first or last:
            set_names(user, first, last)

    if data.city_id is not None:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == data.city_id)
        )).scalar_one_or_none()
        if city_name is None:
            raise HTTPException(status_code=404, detail="Город не найден")
        user.city_id = data.city_id

    if data.telegram_username is not None:
        mp.telegram_username = data.telegram_username.strip().lstrip("@") or None
    if data.description is not None:
        mp.description = data.description.strip() or None
    if data.experience_years is not None:
        mp.experience_years = data.experience_years
    if data.cabinet_address is not None:
        mp.cabinet_address = data.cabinet_address.strip() or None
    if data.certificates is not None:
        mp.certificates = [
            cert.model_dump(exclude_none=True) for cert in data.certificates
        ]
    if data.auto_confirm is not None:
        mp.auto_confirm = bool(data.auto_confirm)
    if data.auto_complete is not None:
        mp.auto_complete = bool(data.auto_complete)
    if data.prefer_master_cabinet is not None:
        mp.prefer_master_cabinet = bool(data.prefer_master_cabinet)

    # Photo and emoji preset are mutually exclusive. The reused form always
    # sends both keys, so null means "clear" when the key is present.
    if "avatar_preset" in data.model_fields_set:
        if (data.avatar_preset is not None
                and data.avatar_preset not in AVATAR_PRESETS):
            raise HTTPException(status_code=400,
                                detail="Неизвестный стандартный аватар")
        mp.avatar_preset = data.avatar_preset
        if data.avatar_preset is not None:
            mp.avatar_url = None
    if "avatar_url" in data.model_fields_set and mp.avatar_preset is None:
        mp.avatar_url = (data.avatar_url or "").strip() or None

    return mp


def _draft_response(
    user: User,
    mp: Optional[MasterProfile],
    profile: dict,
    readiness: dict,
) -> dict:
    return {
        "status": _draft_status(user, mp),
        "profile": profile,
        "readiness": readiness,
        "can_activate": (
            user.role == UserRole.CLIENT and all(readiness.values())
        ),
    }


def _missing_profile_items(readiness: dict) -> list[str]:
    labels = {
        "names": "имя и фамилия",
        "cabinet_address": "адрес кабинета с номером дома",
        "phone": "телефон",
        "verified_email": "подтверждённая почта",
        "social": "привязанная соцсеть (VK ID, Яндекс или MAX)",
    }
    return [label for key, label in labels.items() if not readiness.get(key)]


@router.get("/become-master", response_model=dict)
async def get_master_draft(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Draft state + the same profile shape as /admin/profile."""
    if user.role == UserRole.ADMIN:
        raise HTTPException(status_code=403,
                            detail="Суперпользователь не становится мастером")
    mp = await _get_draft(db, user)
    profile, readiness = await master_profile_snapshot(
        db, user, mp, client_address_fallback=True,
    )
    return _draft_response(user, mp, profile, readiness)


@router.patch("/become-master", response_model=dict)
@limiter.limit("30/minute")
async def save_master_draft(
    request: Request,
    data: MasterDraftRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the master profile draft without activating anything."""
    if user.role != UserRole.CLIENT:
        raise HTTPException(status_code=400,
                            detail="Кабинет мастера уже активирован")
    mp = await _get_draft(db, user)
    mp = await _apply_draft(db, user, mp, data)
    await log_action(db, user.id, "master_draft", "auth", user.id,
                     "Черновик профиля мастера обновлён", level="info")
    await db.commit()
    await db.refresh(user)
    await db.refresh(mp)
    profile, readiness = await master_profile_snapshot(db, user, mp)
    return _draft_response(user, mp, profile, readiness)


@router.post("/become-master/activate", response_model=dict)
@limiter.limit("10/minute")
async def activate_master(
    request: Request,
    response: Response,
    data: MasterDraftRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the form and immediately activate the master cabinet.

    No superadmin approval: the profile itself is the gate. The new access
    JWT (role MASTER) is put into the cookie so the UI can hard-navigate to
    /admin/profile without an extra refresh round-trip.
    """
    if user.role != UserRole.CLIENT:
        raise HTTPException(status_code=400,
                            detail="Кабинет мастера уже активирован")
    if not data.accept_master_terms:
        raise HTTPException(
            status_code=400,
            detail="Подтвердите принятие условий для мастеров",
        )

    mp = await _get_draft(db, user)
    mp = await _apply_draft(db, user, mp, data)
    await db.flush()
    _, readiness = await master_profile_snapshot(db, user, mp)
    missing = _missing_profile_items(readiness)
    if missing:
        # Keep the latest draft fields: the person can fix one item and retry.
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail="Для активации заполните: " + ", ".join(missing),
        )

    # The social avatar is a valid master photo if none was chosen.
    if not mp.avatar_url and not mp.avatar_preset and user.avatar_url:
        mp.avatar_url = user.avatar_url

    mp.is_active = True
    mp.status = "active"
    user.role = UserRole.MASTER
    user.master_terms_accepted_at = datetime.now(dt_timezone.utc)
    user.master_terms_version = service.MASTER_TERMS_VERSION
    from app.services.billing import link_referral_to_master, start_master_trial
    await start_master_trial(db, mp)
    await link_referral_to_master(db, user, mp)
    await log_action(db, user.id, "activate", "auth", user.id,
                     "Кабинет мастера активирован", level="info")
    await send_master_activated_bell(db, user.id)
    await db.commit()
    await db.refresh(user)
    await db.refresh(mp)

    prefer_master = await master_landing_preference(db, user)
    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "is_admin": user.role == UserRole.ADMIN,
        "prefer_master": prefer_master,
    })
    set_auth_cookies(response, access_token, request.cookies.get("refresh_token"))

    profile, readiness = await master_profile_snapshot(db, user, mp)
    logger.info("Master self-activated: user_id=%s profile_id=%s", user.id, mp.id)
    return {
        "detail": "Кабинет мастера активирован",
        "status": "active",
        "profile": profile,
        "readiness": readiness,
        "can_activate": False,
        "access_token": access_token,
    }


@router.post("/become-master/photo", response_model=dict)
@limiter.limit("20/minute")
async def upload_draft_photo(
    request: Request,
    file: UploadFile = File(...),
    kind: str = Query("avatar", description="avatar|cert"),
    user: User = Depends(require_client),
):
    """Upload an optional photo while filling the master draft.

    Clients cannot use the master-only /admin/profile/avatar endpoint before
    activation; this stores the same image format under the same public
    /static/avatars directory. The returned URL goes into the draft payload
    (photo or certificate).
    """
    if kind not in ("avatar", "cert"):
        raise HTTPException(status_code=400, detail="kind: avatar|cert")
    if not is_image_content_type(file.content_type):
        raise HTTPException(status_code=400, detail=IMAGE_TYPE_ERROR)
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(payload) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail=IMAGE_SIZE_ERROR)
    from app.utils.images import downscale_image
    try:
        payload, ext = downscale_image(payload, file.content_type)
    except ValueError:
        logger.warning("Master draft photo rejected as invalid: user=%s", user.id)
        raise HTTPException(
            status_code=400,
            detail="Не удалось распознать изображение. JPEG, PNG, WebP или HEIC.",
        )
    os.makedirs(AVATAR_DIR, exist_ok=True)
    filename = f"user_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    with open(os.path.join(AVATAR_DIR, filename), "wb") as f:
        f.write(payload)
    url = f"{AVATAR_URL_PREFIX}/{filename}"
    logger.info("Master draft photo uploaded: user=%s kind=%s url=%s",
                user.id, kind, url)
    return {"avatar_url": url}


# ─── Password management (1.79.0) ────────────────────────────────────

@router.post("/password/change")
@limiter.limit("10/minute")
async def change_password(
    request: Request,
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password for a client/admin account (masters are social-only)."""
    try:
        await service.change_password(user, req.current_password,
                                      req.new_password, db)
        return {"message": "Пароль изменён"}
    except HTTPException:
        logger.warning("Change password failed: user_id=%s", user.id)
        raise
    except Exception as e:
        logger.error("Change password failed (unexpected): user_id=%s, error=%s",
                     user.id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка смены пароля")


@router.post("/password/forgot")
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    req: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """«Забыли пароль»: email a reset code.

    The reply is identical for known and unknown addresses — no account
    enumeration; the address owner either gets a letter or does not.
    """
    try:
        await service.request_password_reset(req.email, db)
    except Exception as e:
        logger.error("Forgot password failed (unexpected): email=%s, error=%s",
                     req.email, e, exc_info=True)
    return {"message": "Если такая почта есть в системе, мы отправили код. "
                       "Проверьте почту и папку «Спам»."}


@router.post("/password/reset", response_model=TokenResponse)
@limiter.limit("10/minute")
async def reset_password(
    request: Request,
    response: Response,
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set a new password with the emailed code; logs the user in."""
    try:
        user = await service.reset_password(req.email, req.code,
                                            req.new_password, db)
        access_token, refresh_value = await service.issue_session(user, db)
        await log_action(
            db, user.id, "login", "auth", user.id,
            f"Вход после сброса пароля: {user.email or user.phone}",
            level="info",
        )
        await db.commit()
        _set_auth_cookies(response, access_token, refresh_value)
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Reset password failed: email=%s", req.email)
        raise
    except Exception as e:
        logger.error("Reset password failed (unexpected): email=%s, error=%s",
                     req.email, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка сброса пароля")


# ─── 2-Step Consent Flow (152-FZ, 1.80.0) ──────────────────────────

class ConsentCompleteRequest(BaseModel):
    """Complete the 2-step consent flow."""
    challenge: str = Field(min_length=1)
    consent: bool = True


@router.post("/consent/complete", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def consent_complete(
    request: Request,
    response: Response,
    req: ConsentCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete the 2-step consent flow.

    The frontend calls this after the user checks the consent checkbox.
    The challenge token (from /phone/status, /vk/verify, /yandex/verify,
    or /max/verify) identifies the pending user. If consent is given,
    the user is committed and a JWT session is returned.
    """
    payload = service._decode_challenge_token(req.challenge)
    user_id = int(payload["sub"])
    if user_id == 0:
        # phone/status challenge — that path registers via /register-unified.
        raise HTTPException(
            status_code=400,
            detail="Сессия не найдена. Начните вход заново.",
        )
    if not req.consent:
        raise HTTPException(
            status_code=400,
            detail=(
                "Подтвердите согласие на обработку персональных данных — "
                "без него регистрация невозможна"
            ),
        )
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=400,
            detail="Сессия не найдена. Начните вход заново.",
        )
    if user.consent_at is not None:
        # Already consented and committed — just log in.
        access_token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "last_name": user.last_name,
            "is_admin": user.role == UserRole.ADMIN,
            "prefer_master": await master_landing_preference(db, user),
        })
        refresh_value, expires_at = create_refresh_token_payload(
            user.id, user.email or "")
        db.add(RefreshToken(user_id=user.id, token=refresh_value,
                            expires_at=expires_at))
        await db.commit()
        _set_auth_cookies(response, access_token, refresh_value)
        return {"access_token": access_token, "token_type": "bearer"}

    # Consent is required (guarded above); commit_pending_user stamps
    # consent_at + policy/offer versions, creates the ClientProfile and
    # writes the welcome bell.
    await service.commit_pending_user(user, db, consent=req.consent)

    # Mint JWT session.
    access_token, refresh_value = await service.complete_consent_flow(
        user, db, consent=req.consent)
    _set_auth_cookies(response, access_token, refresh_value)
    return {"access_token": access_token, "token_type": "bearer"}
