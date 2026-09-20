from fastapi import APIRouter, HTTPException, Depends, status, Response, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from app.database import get_db
from app.models.master import Master
from app.models.client import Client
from app.models.refresh_token import RefreshToken
from app.schemas.master import MasterCreate, MasterResponse
from app.schemas.client import ClientResponse
from app.schemas.auth import TokenResponse, TokenRefreshResponse, TokenRefreshRequest
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone as dt_timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import settings
from app.logging_config import get_logger
import secrets

logger = get_logger(__name__)

class LoginRequest(BaseModel):
    email: str
    password: str

class ClientLoginRequest(BaseModel):
    phone: str

router = APIRouter()
security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.SECRET_KEY
REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = (datetime.now(dt_timezone.utc) +
              (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token_payload(master_id: int, email: str) -> tuple[str, datetime]:
    to_encode = {
        "sub": str(master_id),
        "email": email,
        "type": "refresh",
        "jti": secrets.token_urlsafe(32),
    }
    expire = datetime.now(dt_timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM), expire


@router.post("/register", response_model=MasterResponse, status_code=status.HTTP_201_CREATED)
async def register_master(master: MasterCreate, db: AsyncSession = Depends(get_db)):
    logger.info("Запрос на регистрацию мастера: %s", master.email)
    result = await db.execute(select(Master).where(Master.email == master.email))
    if result.scalar_one_or_none():
        logger.warning("Регистрация заблокирована — мастер уже существует: %s", master.email)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Мастер с таким email уже существует")

    new_master = Master(
        name=master.name, email=master.email,
        hashed_password=pwd_context.hash(master.password),
        phone=master.phone, telegram_username=master.telegram_username
    )
    db.add(new_master)
    await db.commit()
    await db.refresh(new_master)
    logger.info("Мастер успешно зарегистрирован: %s", master.email)
    return new_master


@router.post("/login", response_model=TokenResponse)
async def login(response: Response, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login master — returns access token in response body, refresh token in httpOnly cookie."""
    logger.info("Запрос на вход мастера: %s", req.email)
    result = await db.execute(select(Master).where(Master.email == req.email))
    master = result.scalar_one_or_none()

    if not master or not pwd_context.verify(req.password, master.hashed_password):
        logger.warning("Неудачная попытка входа: %s", req.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Неверный email или пароль")

    access_token = create_access_token({
        "sub": str(master.id), "is_admin": master.is_admin, "name": master.name
    })

    refresh_token_value, expires_at = create_refresh_token_payload(master.id, master.email)
    db.add(RefreshToken(user_id=master.id, token=refresh_token_value, expires_at=expires_at))
    await db.commit()

    response.set_cookie(
        key="refresh_token", value=refresh_token_value,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    # access_token in non-httponly cookie so frontend can read it for Authorization header
    response.set_cookie(
        key="access_token", value=access_token,
        httponly=False,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    logger.info("Мастер успешно вошёл в систему: %s", req.email)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/client/login", response_model=TokenResponse)
async def client_login(req: ClientLoginRequest, db: AsyncSession = Depends(get_db)):
    logger.info("Запрос на вход клиента: %s", req.phone)
    result = await db.execute(select(Client).where(Client.phone == req.phone))
    client = result.scalar_one_or_none()

    if not client:
        logger.warning("Клиент не найден: %s", req.phone)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден")

    access_token = create_access_token({"sub": str(client.id), "type": "client"})
    logger.info("Клиент успешно вошёл в систему: %s", req.phone)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """Refresh access token with rotation."""
    cookie_token = request.cookies.get("refresh_token")
    if not cookie_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = jwt.decode(cookie_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
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

    if not stored_token or stored_token.expires_at < datetime.now(dt_timezone.utc):
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

    response = Response()
    response.set_cookie(
        key="refresh_token", value=new_refresh_value,
        httponly=True, secure=not settings.DEBUG, samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600, path="/",
    )
    response.set_cookie(
        key="access_token", value=new_access,
        httponly=False, secure=not settings.DEBUG, samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
    )
    response.body = b'{"access_token":"' + new_access.encode() + b'","token_type":"bearer"}'

    return TokenRefreshResponse(access_token=new_access)


@router.post("/logout")
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    """Logout — revoke all refresh tokens for current user."""
    cookie_token = request.cookies.get("refresh_token")
    if cookie_token:
        try:
            payload = jwt.decode(cookie_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            user_id = int(payload["sub"])
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)
                .values(is_revoked=True, revoked_at=datetime.now(dt_timezone.utc))
            )
            await db.commit()
        except JWTError:
            pass

    response = Response()
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="access_token", path="/")
    return {"detail": "Logged out"}
