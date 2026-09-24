"""Authentication API endpoints — register, login, OTP, refresh, logout."""
from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from datetime import datetime, timezone as dt_timezone
from pydantic import BaseModel

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


class LoginRequest(BaseModel):
    email: str
    password: str


class ClientLoginRequest(BaseModel):
    phone: str


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
    if user_data.role != UserRole.MASTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Только мастера могут зарегистрироваться через этот endpoint"
        )

    new_user = await service.register_master(user_data, db)

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
async def login(response: Response, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login master by email+password — returns access token in response body, refresh token in httpOnly cookie."""
    access_token, user = await service.login_master(req.email, req.password, db)

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


@router.post("/client/login", response_model=TokenResponse)
async def client_login(req: ClientLoginRequest, db: AsyncSession = Depends(get_db)):
    """Legacy client login by phone (no password)."""
    access_token, user = await service.login_client_legacy(req.phone, db)
    return {"access_token": access_token, "token_type": "bearer"}


# ─── OTP Authentication ──────────────────────────────────────────────

@router.post("/send-otp", response_model=OtpResponse)
async def send_otp(req: SendOtpRequest, db: AsyncSession = Depends(get_db)):
    """Send OTP code to phone number."""
    try:
        await service.send_otp(req.phone, db)
        return {"message": "Код отправлен"}
    except Exception as e:
        logger.error("Error sending OTP: %s", e)
        raise HTTPException(status_code=500, detail="Не удалось отправить код")


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(req: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    """Verify OTP code and login/create user."""
    access_token, user = await service.verify_otp(req.phone, req.code, db)
    return {"access_token": access_token, "token_type": "bearer"}


# ─── Token Refresh ────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """Refresh access token with rotation."""
    cookie_token = request.cookies.get("refresh_token")
    if not cookie_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = jwt.decode(cookie_token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == cookie_token,
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        )
    )
    stored_token = result.scalar_one_or_none()

    if not stored_token or stored_token.expires_at < datetime.now(dt_timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
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
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)
                .values(is_revoked=True, revoked_at=datetime.now(dt_timezone.utc))
            )
            await db.commit()
        except JWTError:
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
    access_token, user = await service.login_unified(req.identifier, req.password, db)

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


# ─── Unified Registration ────────────────────────────────────────────

@router.post("/register-unified", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_unified(
    req: UnifiedRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Full registration with role selection (client or master)."""
    from app.modules.auth import service as auth_service
    from app.models.user import UserRole

    # Determine role
    role = UserRole.MASTER if req.is_master else UserRole.CLIENT

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует"
        )

    # Check if phone already exists
    result = await db.execute(select(User).where(User.phone == req.phone))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким телефоном уже существует"
        )

    # Create user
    new_user = User(
        name=req.name,
        email=req.email,
        phone=req.phone,
        hashed_password=service.hash_password(req.password),
        role=role,
        city_id=req.city_id,
        is_verified=True,  # auto-verify on registration
    )
    db.add(new_user)
    await db.flush()

    # Create profile based on role
    if role == UserRole.MASTER:
        from app.models.master_profile import MasterProfile
        master_profile = MasterProfile(
            user_id=new_user.id,
            telegram_username=req.telegram_username,
        )
        db.add(master_profile)
    else:
        from app.models.client_profile import ClientProfile
        client_profile = ClientProfile(user_id=new_user.id)
        db.add(client_profile)

    await db.commit()
    await db.refresh(new_user)

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
