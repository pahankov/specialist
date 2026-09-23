"""Authentication business logic — registration, login, password verification."""
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from app.models.master import Master
from app.models.client import Client
from app.models.refresh_token import RefreshToken
from app.schemas.master import MasterCreate
from app.logging_config import get_logger
from app.config import settings
from datetime import datetime, timezone as dt_timezone

logger = get_logger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


async def register_master(master_data: MasterCreate, db: AsyncSession) -> Master:
    """Register a new master. Returns Master instance."""
    logger.info("Регистрация мастера: %s", master_data.email)

    result = await db.execute(select(Master).where(Master.email == master_data.email))
    if result.scalar_one_or_none():
        logger.warning("Регистрация заблокирована — мастер уже существует: %s", master_data.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Мастер с таким email уже существует"
        )

    new_master = Master(
        name=master_data.name,
        email=master_data.email,
        hashed_password=hash_password(master_data.password),
        phone=master_data.phone,
        telegram_username=master_data.telegram_username
    )
    db.add(new_master)
    await db.commit()
    await db.refresh(new_master)
    logger.info("Мастер успешно зарегистрирован: %s", master_data.email)
    return new_master


async def login_master(email: str, password: str, db: AsyncSession):
    """Login master. Returns (access_token, master) or raises HTTPException."""
    logger.info("Запрос на вход: %s", email)

    result = await db.execute(select(Master).where(Master.email == email))
    master = result.scalar_one_or_none()

    if not master or not verify_password(password, master.hashed_password):
        logger.warning("Неудачная попытка входа: %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    from app.modules.auth.token import create_access_token
    from app.models.refresh_token import RefreshToken

    role = "Суперпользователь" if master.is_admin else "Мастер"
    access_token = create_access_token({
        "sub": str(master.id), "is_admin": master.is_admin, "name": master.name
    })

    from app.modules.auth.token import create_refresh_token_payload
    refresh_token_value, expires_at = create_refresh_token_payload(master.id, master.email)
    db.add(RefreshToken(user_id=master.id, token=refresh_token_value, expires_at=expires_at))
    await db.commit()

    logger.info("%s успешно вошёл в систему: %s", role, email)
    return access_token, master


async def login_client(phone: str, db: AsyncSession):
    """Login client by phone. Returns (access_token, client) or raises HTTPException."""
    logger.info("Запрос на вход клиента: %s", phone)

    result = await db.execute(select(Client).where(Client.phone == phone))
    client = result.scalar_one_or_none()

    if not client:
        logger.warning("Клиент не найден: %s", phone)
        raise HTTPException(status_code=404, detail="Клиент не найден")

    from app.modules.auth.token import create_access_token
    access_token = create_access_token({"sub": str(client.id), "type": "client"})
    logger.info("Клиент успешно вошёл в систему: %s", phone)
    return access_token, client
