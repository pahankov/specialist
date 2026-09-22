"""Authentication API endpoints — register, login, refresh, logout."""
from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from fastapi.security import HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from datetime import datetime, timezone as dt_timezone
from pydantic import BaseModel

from app.database import get_db
from app.models.master import Master
from app.models.refresh_token import RefreshToken
from app.schemas.master import MasterCreate
from app.schemas.auth import TokenResponse, TokenRefreshResponse, TokenRefreshRequest
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
    master: MasterCreate,
    db: AsyncSession = Depends(get_db)
):
    new_master = await service.register_master(master, db)
    return {
        "id": new_master.id,
        "name": new_master.name,
        "email": new_master.email,
        "phone": new_master.phone,
        "telegram_username": new_master.telegram_username,
        "is_active": new_master.is_active,
        "is_admin": new_master.is_admin,
        "created_at": new_master.created_at.isoformat() if new_master.created_at else None,
        "updated_at": new_master.updated_at.isoformat() if new_master.updated_at else None,
    }


# ─── Login ────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(response: Response, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login master — returns access token in response body, refresh token in httpOnly cookie."""
    access_token, master = await service.login_master(req.email, req.password, db)

    # Get the most recent refresh token for this master
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == master.id,
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
    access_token, client = await service.login_client(req.phone, db)
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

    result = await db.execute(select(Master).where(Master.id == user_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=401, detail="User not found")

    stored_token.is_revoked = True
    stored_token.revoked_at = datetime.now(dt_timezone.utc)

    new_access = create_access_token({
        "sub": str(master.id), "is_admin": master.is_admin, "name": master.name
    })
    new_refresh_value, new_expires = create_refresh_token_payload(master.id, master.email)
    db.add(RefreshToken(user_id=master.id, token=new_refresh_value, expires_at=new_expires))

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
