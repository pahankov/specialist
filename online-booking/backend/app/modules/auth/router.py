"""Authentication API endpoints — register, login, OTP, refresh, logout."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from datetime import datetime, timezone as dt_timezone

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.refresh_token import RefreshToken
from app.models.country import Country
from app.schemas.user import UserCreate, UserLoginByEmail, UserLoginByPhone
from app.schemas.otp import SendOtpRequest, VerifyOtpRequest, OtpResponse
from app.schemas.auth import TokenResponse, TokenRefreshResponse, TokenRefreshRequest, UnifiedLoginRequest, UnifiedRegisterRequest
from app.config import settings
from app.logging_config import get_logger
from app.services.audit import log_action
from app.modules.auth import service
from app.modules.auth.token import create_access_token, create_refresh_token_payload
from app.dependencies.auth import get_current_user
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
    """Login master by email+password — returns access token in response body, refresh token in httpOnly cookie."""
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


@router.post("/client/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def client_login(request: Request, req: UserLoginByPhone, db: AsyncSession = Depends(get_db)):
    """Legacy client login by phone (no password)."""
    logger.info("Client login attempt by phone: %s", req.phone)
    try:
        access_token, user = await service.login_client_legacy(req.phone, db)
        logger.info("Client login successful: user_id=%s, phone=%s", user.id, user.phone)
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Client login failed: phone=%s", req.phone)
        raise
    except Exception as e:
        logger.error("Client login failed (unexpected): phone=%s, error=%s", req.phone, e, exc_info=True)
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
        "is_admin": user.role == UserRole.ADMIN,
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
    """Login with email OR phone + password. Works for both clients and masters."""
    logger.info("Unified login attempt: identifier=%s", req.identifier)
    try:
        access_token, user = await service.login_unified(req.identifier, req.password, db)
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
            db, user.id, "login", "auth", user.id,
            f"Вход: {user.email or user.phone} ({user.role.value})", level="info",
        )
        await db.commit()
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Unified login failed: identifier=%s", req.identifier)
        raise
    except Exception as e:
        logger.error("Unified login failed (unexpected): identifier=%s, error=%s", req.identifier, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка авторизации")


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
    """
    logger.info("Quick register: phone=%s", req.phone)
    try:
        new_user = await service.register_unified(
            phone=req.phone,
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
        logger.warning("Quick register failed: phone=%s", req.phone)
        raise
    except Exception as e:
        logger.error("Quick register failed (unexpected): phone=%s, error=%s", req.phone, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка регистрации")


# ─── Become master (client applies, admin activates) ──────────────

class BecomeMasterRequest(BaseModel):
    cabinet_address: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    experience_years: Optional[int] = Field(default=None, ge=0, le=80)


@router.post("/become-master", response_model=dict)
@limiter.limit("10/minute")
async def become_master(
    request: Request,
    data: BecomeMasterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply for a master profile (strict verification, no instant access).

    Creates an INACTIVE MasterProfile; the account stays CLIENT until a
    superadmin activates it (toggle flips the role too). Nothing is
    published, no panel access — this closes the one-click self-promotion.
    """
    if user.role != UserRole.CLIENT:
        raise HTTPException(status_code=400, detail="Вы уже мастер")
    existing = (await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == user.id)
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400,
                            detail="Заявка уже подана, дождитесь проверки")
    db.add(MasterProfile(
        user_id=user.id, status="inactive", is_active=False,
        cabinet_address=(data.cabinet_address or "").strip() or None,
        description=(data.description or "").strip() or None,
        experience_years=data.experience_years,
    ))
    await log_action(db, user.id, "apply", "auth", user.id,
                     "Заявка на мастера", level="info")
    await db.commit()
    logger.info("User %s applied for master", user.id)
    return {"detail": "Заявка отправлена, профиль появится после проверки"}
