"""Authentication API endpoints — register, login, OTP, refresh, logout."""
from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from datetime import datetime, timezone as dt_timezone

from app.database import get_db
from app.models.user import User, UserRole
from app.models.refresh_token import RefreshToken
from app.models.country import Country
from app.schemas.user import UserCreate, UserLoginByEmail, UserLoginByPhone
from app.schemas.otp import SendOtpRequest, VerifyOtpRequest, OtpResponse
from app.schemas.auth import TokenResponse, TokenRefreshResponse, TokenRefreshRequest, UnifiedLoginRequest, UnifiedRegisterRequest
from app.config import settings
from app.logging_config import get_logger
from app.modules.auth import service
from app.modules.auth.token import create_access_token, create_refresh_token_payload

logger = get_logger(__name__)

router = APIRouter()

security = HTTPBearer(auto_error=False)


def _set_auth_cookies(
    response: Response, access_token: str, refresh_token_value: str
) -> None:
    """Helper: set both access and refresh tokens as cookies."""
    response.set_cookie(
        key="refresh_token", value=refresh_token_value,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    response.set_cookie(
        key="access_token", value=access_token,
        httponly=False,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


# ─── Registration ─────────────────────────────────────────────────────

@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_master(
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

    return {
        "id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
        "phone": new_user.phone,
        "role": new_user.role.value,
        "city_id": new_user.city_id,
        "is_active": new_user.is_active,
        "is_verified": new_user.is_verified,
        "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
        "updated_at": new_user.updated_at.isoformat() if new_user.updated_at else None,
    }


# ─── Login ────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(response: Response, req: UserLoginByEmail, db: AsyncSession = Depends(get_db)):
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
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Login failed (HTTP): email=%s", req.email)
        raise
    except Exception as e:
        logger.error("Login failed (unexpected): email=%s, error=%s", req.email, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка авторизации")


@router.post("/client/login", response_model=TokenResponse)
async def client_login(req: UserLoginByPhone, db: AsyncSession = Depends(get_db)):
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
async def send_otp(req: SendOtpRequest, db: AsyncSession = Depends(get_db)):
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
async def verify_otp(req: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
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
    except JWTError as e:
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

    if not stored_token or stored_token.expires_at < datetime.now(dt_timezone.utc):
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
            await db.commit()
        except JWTError:
            logger.debug("Logout: invalid JWT in cookie, skipping token revocation")
            pass

    response = Response(content='{"detail":"Logged out"}')
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="access_token", path="/")
    return response


# ─── Unified Login ───────────────────────────────────────────────────

@router.post("/login-unified", response_model=TokenResponse)
async def login_unified(
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
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        logger.warning("Unified login failed: identifier=%s", req.identifier)
        raise
    except Exception as e:
        logger.error("Unified login failed (unexpected): identifier=%s, error=%s", req.identifier, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка авторизации")


# ─── Unified Registration ────────────────────────────────────────────

@router.post("/register-unified", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_unified(
    req: UnifiedRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Full registration with role selection (client or master)."""
    logger.info(
        "Unified register: name=%s, email=%s, phone=%s, is_master=%s",
        req.name, req.email, req.phone, req.is_master
    )
    try:
        new_user = await service.register_unified(
            name=req.name,
            email=req.email,
            phone=req.phone,
            password=req.password,
            city_id=req.city_id,
            telegram_username=req.telegram_username,
            is_master=req.is_master,
            db=db,
        )
        logger.info(
            "Unified register successful: user_id=%s, role=%s",
            new_user.id, new_user.role.value
        )

        return {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email,
            "phone": new_user.phone,
            "role": new_user.role.value,
            "city_id": new_user.city_id,
            "is_master": req.is_master,
            "telegram_username": req.telegram_username,
            "is_active": new_user.is_active,
            "is_verified": new_user.is_verified,
            "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
        }
    except HTTPException:
        logger.warning("Unified register failed: name=%s", req.name)
        raise
    except Exception as e:
        logger.error("Unified register failed (unexpected): name=%s, error=%s", req.name, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка регистрации")
