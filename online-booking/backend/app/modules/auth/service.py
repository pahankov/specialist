"""Authentication business logic — registration, login, password verification.

Updated to use the unified User model with role-based access.
"""
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.client_profile import ClientProfile
from app.models.refresh_token import RefreshToken
from app.models.otp_code import OtpCode
from app.schemas.user import UserCreate, UserLoginByEmail, UserLoginByPhone
from app.schemas.otp import SendOtpRequest
from app.services.names import name_fields as _name_fields
from app.logging_config import get_logger
from app.config import settings
from app.utils.security import hash_password, verify_password, hash_otp_code
from app.utils.tokens import create_access_token, create_refresh_token_payload
from datetime import datetime, timezone as dt_timezone, timedelta
import secrets

logger = get_logger(__name__)

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM


# ─── Registration ─────────────────────────────────────────────────────

async def register_master(user_data: UserCreate, db: AsyncSession) -> User:
    """Register a new master. Returns User instance with MasterProfile."""
    logger.info("Регистрация мастера: %s", user_data.email)

    # Check email uniqueness
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Мастер с таким email уже существует"
            )

    # Check phone uniqueness
    if user_data.phone:
        result = await db.execute(select(User).where(User.phone == user_data.phone))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Мастер с таким телефоном уже существует"
            )

    # Create user
    full_name, last_name = _name_fields(user_data.name)
    new_user = User(
        name=full_name,
        last_name=last_name,
        email=user_data.email,
        phone=user_data.phone,
        hashed_password=hash_password(user_data.password) if user_data.password else None,
        role=UserRole.MASTER,
        city_id=user_data.city_id,
        is_verified=bool(user_data.email),  # auto-verify if email provided
    )
    db.add(new_user)
    await db.flush()  # Get user ID before creating profile

    # Create master profile
    master_profile = MasterProfile(
        user_id=new_user.id,
        telegram_username=None,  # will be set later
    )
    db.add(master_profile)

    await db.commit()
    await db.refresh(new_user)
    await db.refresh(master_profile)

    logger.info("Мастер успешно зарегистрирован: %s", user_data.email)
    return new_user


# ─── Login ────────────────────────────────────────────────────────────

async def login_master(email: str, password: str, db: AsyncSession) -> tuple[str, User]:
    """Login master by email+password. Returns (access_token, user)."""
    logger.info("Запрос на вход мастера: %s", email)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        logger.warning("Неудачная попытка входа: %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )

    if user.is_active is False:
        logger.warning("Вход заблокированного мастера: %s", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован. Обратитесь к администратору."
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "is_admin": user.role == UserRole.ADMIN,
    })

    refresh_token_value, expires_at = create_refresh_token_payload(user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_token_value, expires_at=expires_at))
    await db.commit()
    logger.debug("Refresh token stored for user_id=%s, expires=%s", user.id, expires_at)

    logger.info("Мастер успешно вошёл в систему: %s", email)
    return access_token, user


# ─── OTP Authentication ──────────────────────────────────────────────

async def send_otp(phone: str, db: AsyncSession) -> None:
    """Send OTP code to phone. Creates OtpCode record."""
    logger.info("Запрос OTP на номер: %s", phone)

    # Generate 6-digit numeric code (VerifyOtpRequest.validate_code requires isdigit)
    code = f"{secrets.randbelow(1_000_000):06d}"

    # Hash and store
    code_hash = hash_otp_code(code)
    expires_at = datetime.now(dt_timezone.utc) + timedelta(minutes=5)

    otp = OtpCode(
        phone=phone,
        code_hash=code_hash,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(otp)
    await db.commit()

    # Send via SMS provider
    from app.services.sms.provider import get_sms_provider
    provider = get_sms_provider()
    await provider.send(phone, code)

    logger.info("OTP отправлен на %s", phone)


async def verify_otp(phone: str, code: str, db: AsyncSession) -> tuple[str, User]:
    """Verify OTP code and login/create user. Returns (access_token, user)."""
    logger.info("Проверка OTP для номера: %s", phone)

    # Find latest unused OTP
    result = await db.execute(
        select(OtpCode)
        .where(OtpCode.phone == phone, OtpCode.is_used == False)
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()

    if not otp:
        raise HTTPException(status_code=400, detail="Код не найден. Запросите новый.")

    if datetime.now(dt_timezone.utc).replace(tzinfo=None) > otp.expires_at:
        raise HTTPException(status_code=410, detail="Код истёк. Запросите новый.")

    if hash_otp_code(code) != otp.code_hash:
        raise HTTPException(status_code=400, detail="Неверный код")

    # Mark as used
    otp.is_used = True
    await db.commit()

    # Find or create user
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    if not user:
        # Create new client user
        logger.info("Creating new client via OTP: phone=%s", phone)
        user = User(
            name="",  # will be set later
            phone=phone,
            role=UserRole.CLIENT,
            hashed_password=None,  # OTP-only auth
            is_verified=False,
        )
        db.add(user)
        await db.flush()

        from app.services.clients import get_or_create_profile
        await get_or_create_profile(db, user)
        await db.commit()
        await db.refresh(user)
        logger.info("New client created via OTP: user_id=%s, phone=%s", user.id, phone)

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "is_admin": user.role == UserRole.ADMIN,
    })

    refresh_token_value, expires_at = create_refresh_token_payload(user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_token_value, expires_at=expires_at))
    await db.commit()

    logger.info("Клиент успешно вошёл через OTP: %s", phone)
    return access_token, user


# ─── Legacy compatibility ────────────────────────────────────────────

async def login_client_legacy(phone: str, db: AsyncSession) -> tuple[str, User]:
    """Legacy client login by phone (no password). Returns (access_token, user)."""
    logger.info("Запрос на вход клиента (legacy): %s", phone)

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("Клиент не найден: %s", phone)
        raise HTTPException(status_code=404, detail="Клиент не найден")

    if user.is_active is False:
        logger.warning("Вход заблокированного клиента: %s", phone)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован. Обратитесь к администратору."
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
    })
    logger.info("Клиент успешно вошёл в систему: %s", phone)
    return access_token, user


# ─── Unified Login ───────────────────────────────────────────────────

async def login_unified(identifier: str, password: str, db: AsyncSession) -> tuple[str, User]:
    """Login with email OR phone + password. Works for both clients and masters."""
    logger.info("Unified login attempt: %s", identifier)

    # Try to find user by email
    result = await db.execute(select(User).where(User.email == identifier))
    user = result.scalar_one_or_none()

    # If not found by email, try by phone
    if not user:
        result = await db.execute(select(User).where(User.phone == identifier))
        user = result.scalar_one_or_none()

    if not user:
        logger.warning("User not found: %s", identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email/телефон или пароль"
        )

    if not user.hashed_password or not verify_password(password, user.hashed_password):
        logger.warning("Invalid password for: %s", identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email/телефон или пароль"
        )

    if user.is_active is False:
        logger.warning("Вход заблокированного пользователя: %s", identifier)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован. Обратитесь к администратору."
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "is_admin": user.role == UserRole.ADMIN,
    })

    refresh_token_value, expires_at = create_refresh_token_payload(user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_token_value, expires_at=expires_at))
    await db.commit()

    logger.info("User successfully logged in: %s", identifier)
    return access_token, user


# ─── Unified Registration ────────────────────────────────────────────

# Legal document versions accepted at registration (consent checkbox).
# Bump together with the frontend /privacy and /offer pages.
POLICY_VERSION = "2026-10-12"
OFFER_VERSION = "2026-10-12"

async def register_unified(
    phone: str,
    password: str,
    db: AsyncSession,
    consent: bool = False,
) -> User:
    """Quick registration: phone + password, everyone a CLIENT.

    Minimal by design — name/email/address/city are refined later in the
    client cabinet profile. Becoming a master is a separate, admin-approved
    application (/become-master), never this path. `name` is nullable and
    left empty here; the display name is filled in once the user edits
    their profile.
    """
    logger.info("Quick registration: %s", phone)

    # Check phone uniqueness
    result = await db.execute(select(User).where(User.phone == phone))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким телефоном уже существует"
        )

    # Create user (CLIENT role; name/email filled later in the profile).
    # Consent checkbox (offer + privacy policy) is stamped as legal proof.
    # `name` starts empty (column is non-nullable) — filled in the cabinet.
    new_user = User(
        name="",
        phone=phone,
        hashed_password=hash_password(password),
        role=UserRole.CLIENT,
        is_verified=True,
        consent_at=(datetime.now(dt_timezone.utc) if consent else None),
        consent_policy_version=(POLICY_VERSION if consent else None),
        consent_offer_version=(OFFER_VERSION if consent else None),
    )
    db.add(new_user)
    await db.flush()

    # Every registrant gets a client cabinet profile.
    db.add(ClientProfile(user_id=new_user.id))

    await db.commit()
    await db.refresh(new_user)

    logger.info("User successfully registered: %s (role=CLIENT)", phone)
    return new_user

