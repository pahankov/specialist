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
from app.models.master_profile import MasterProfile
from app.models.refresh_token import RefreshToken
from app.models.country import Country
from app.schemas.user import UserCreate, UserLoginByEmail, UserLoginByPhone
from app.schemas.otp import SendOtpRequest, VerifyOtpRequest, OtpResponse
from app.schemas.auth import TokenResponse, TokenRefreshResponse, TokenRefreshRequest, UnifiedLoginRequest, UnifiedRegisterRequest
from app.config import settings
from app.logging_config import get_logger
from app.modules.auth import service
from app.modules.auth.token import create_access_token, create_refresh_token_payload
from app.middleware.rate_limit import limiter

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
@limiter.limit("5/minute")
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
async def login(
    request: Request,
    data: UserLoginByEmail,
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
