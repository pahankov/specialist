"""Authentication business logic — registration, login, password verification.

Updated to use the unified User model with role-based access.
"""
from fastapi import HTTPException, status
from sqlalchemy import update
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
from app.services import email_codes, mailer
from app.services.audit import log_action
from app.services.contacts import (
    CONTACT_EMAIL,
    CONTACT_PHONE,
    ContactTaken,
    InvalidContact,
    attach_contact,
    find_user_by_contact,
    normalize_email,
)
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

    # Uniqueness across the contact model (legacy columns included).
    if user_data.email and await find_user_by_contact(
            db, CONTACT_EMAIL, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Мастер с таким email уже существует"
        )
    if user_data.phone and await find_user_by_contact(
            db, CONTACT_PHONE, user_data.phone):
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
    )
    db.add(new_user)
    await db.flush()  # Get user ID before creating profile

    # Contacts (new model): password accounts land unverified — «парольные
    # аккаунты без верификаций» (подтверждения приходят соцвходом/кодом).
    if new_user.phone:
        await attach_contact(db, new_user, CONTACT_PHONE, new_user.phone)
    if new_user.email:
        await attach_contact(db, new_user, CONTACT_EMAIL, new_user.email)

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

    # Find or create user (contact model first, legacy column as fallback)
    user = await find_user_by_contact(db, CONTACT_PHONE, phone)

    if not user:
        # Create new client user
        logger.info("Creating new client via OTP: phone=%s", phone)
        user = User(
            name="",  # will be set later
            role=UserRole.CLIENT,
            hashed_password=None,  # OTP-only auth
        )
        db.add(user)
        await db.flush()
        # The phone lands as a contact. Unverified on purpose: «телефон
        # подтверждается только соцвходом» — OTP-код в модель верификации
        # телефона не входит.
        await attach_contact(db, user, CONTACT_PHONE, phone, make_primary=True)

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

    # «Единый вход»: the identifier is a contact — email or phone. The
    # contact service owns both the new model and the legacy fallback.
    if "@" in (identifier or ""):
        user = await find_user_by_contact(db, CONTACT_EMAIL, identifier)
    else:
        user = await find_user_by_contact(db, CONTACT_PHONE, identifier)

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


async def phone_status(phone: str, db: AsyncSession) -> dict:
    """Unified entry, step 1: what awaits this phone — вход или регистрация.

    Replies "new" (no account — offer phone+password signup), "password"
    (an account with a password — ask for it) or "social" (an account
    without a password — enter via VK/Яндекс/MAX). The phone arrives
    normalized from the schema; the lookup also covers legacy accounts
    whose number still sits in users.phone.
    """
    user = await find_user_by_contact(db, CONTACT_PHONE, phone)
    if user is None:
        state = "new"
    elif user.hashed_password:
        state = "password"
    else:
        state = "social"
    logger.info("Phone status: %s -> %s", phone, state)
    return {"state": state, "phone": phone}


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

    # A phone may live as a contact (new model) or in the legacy column.
    if await find_user_by_contact(db, CONTACT_PHONE, phone) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким телефоном уже существует"
        )

    # Create user (CLIENT role; name/email filled later in the profile).
    # Consent checkbox (offer + privacy policy) is stamped as legal proof.
    # `name` starts empty (column is non-nullable) — filled in the cabinet.
    # No verification flags: password accounts stay unverified («парольные
    # аккаунты без верификаций»).
    new_user = User(
        name="",
        phone=phone,
        hashed_password=hash_password(password),
        role=UserRole.CLIENT,
        consent_at=(datetime.now(dt_timezone.utc) if consent else None),
        consent_policy_version=(POLICY_VERSION if consent else None),
        consent_offer_version=(OFFER_VERSION if consent else None),
    )
    db.add(new_user)
    await db.flush()

    # Every registrant gets a client cabinet profile.
    db.add(ClientProfile(user_id=new_user.id))

    # The phone lands in the contact model as primary but NOT verified:
    # it is typed at registration and confirmed by nobody yet («Единый
    # вход»: телефон подтверждается только соцвходом).
    await attach_contact(db, new_user, CONTACT_PHONE, phone, make_primary=True)

    await db.commit()
    await db.refresh(new_user)

    logger.info("User successfully registered: %s (role=CLIENT)", phone)
    return new_user


# ─── Password management (1.79.0) ────────────────────────────────────

async def issue_session(user: User, db: AsyncSession) -> tuple[str, str]:
    """Access token + a fresh refresh-token row (NOT committed).

    Used by endpoints that log a user in right after a password action;
    the caller commits and puts the returned refresh value into the
    httpOnly cookie.
    """
    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "is_admin": user.role == UserRole.ADMIN,
    })
    refresh_token_value, expires_at = create_refresh_token_payload(
        user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_token_value,
                        expires_at=expires_at))
    return access_token, refresh_token_value


async def _revoke_all_refresh_tokens(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id,
               RefreshToken.is_revoked == False)  # noqa: E712
        .values(is_revoked=True, revoked_at=datetime.now(dt_timezone.utc))
    )


async def change_password(
    user: User,
    current_password: str,
    new_password: str,
    db: AsyncSession,
) -> None:
    """Change the password of the current account — any role that has one.

    Social / OTP-only accounts have no password by design («пароль
    соц-юзерам не навязываем»): for them this is a 400 with a hint,
    never a silent password creation. Sessions stay alive: the user
    knows their new password already.
    """
    logger.info("Change password request: user_id=%s", user.id)
    if not user.hashed_password:
        logger.warning("Change password denied, no password: user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У аккаунта нет пароля — вы входите через соцсеть",
        )
    if not verify_password(current_password, user.hashed_password):
        logger.warning("Change password: wrong current password, user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль",
        )
    if verify_password(new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Новый пароль совпадает с текущим",
        )
    user.hashed_password = hash_password(new_password)
    await log_action(db, user.id, "password_change", "auth", user.id,
                     "Смена пароля", level="info")
    await db.commit()
    logger.info("Password changed: user_id=%s", user.id)


async def request_password_reset(email: str, db: AsyncSession) -> bool:
    """Send a reset code if the email belongs to an active account.

    Always looks identical from the outside (no account enumeration):
    the caller returns one generic message whatever happens here.
    Accounts without a password may still set one through the reset —
    it is a deliberate user action, not an imposed password.
    """
    try:
        email = normalize_email(email)
    except InvalidContact:
        return False
    user = await find_user_by_contact(db, CONTACT_EMAIL, email)
    if user is None or user.is_active is False:
        logger.info("Password reset for unknown/inactive email: %s", email)
        return False
    code = await email_codes.issue_code(
        db, email, email_codes.PURPOSE_RESET_PASSWORD)
    sent = await mailer.send_password_reset_code(email, code)
    logger.info("Password reset code issued: email=%s sent=%s", email, sent)
    return sent


async def reset_password(
    email: str,
    code: str,
    new_password: str,
    db: AsyncSession,
) -> User:
    """Finish «Забыли пароль»: verify the emailed code, set the password.

    Every existing session is revoked — a reset is a recovery action and
    may follow a compromise; the caller then issues a fresh session for
    the current device.
    """
    logger.info("Password reset attempt: %s", email)
    try:
        await email_codes.verify_code(
            db, email, email_codes.PURPOSE_RESET_PASSWORD, code)
    except email_codes.EmailCodeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    user = await find_user_by_contact(db, CONTACT_EMAIL, email)
    if user is None or user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Аккаунт с такой почтой не найден",
        )

    user.hashed_password = hash_password(new_password)
    await _revoke_all_refresh_tokens(db, user.id)
    # The emailed code just proved this address belongs to the account —
    # land it in the contact model as verified-by-code (idempotent; also
    # covers legacy accounts whose email lived only in users.email).
    try:
        await attach_contact(db, user, CONTACT_EMAIL, email,
                             verified_via="code")
    except (InvalidContact, ContactTaken) as exc:
        logger.warning("Reset: contact verification skipped: %s", exc)
    await log_action(db, user.id, "password_reset", "auth", user.id,
                     "Сброс пароля по коду из письма", level="warning")
    await db.commit()
    logger.info("Password reset done: user_id=%s", user.id)
    return user

