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
from app.models.user_contact import UserContact
from app.schemas.user import UserCreate, UserLoginByEmail, UserLoginByPhone
from app.schemas.otp import SendOtpRequest
from app.services.names import name_fields as _name_fields
from app.services.master_landing import master_landing_preference
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
    normalize_contact_value,
)
from app.logging_config import get_logger
from app.config import settings
from app.utils.security import (
    hash_password,
    verify_password,
    hash_otp_code,
    validate_password_strength,
)
from app.utils.tokens import create_access_token, create_refresh_token_payload
from datetime import datetime, timezone as dt_timezone, timedelta
import secrets
import jwt

logger = get_logger(__name__)

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

# Challenge token TTL: 5 minutes for the 2-step consent flow (152-FZ).
CHALLENGE_TTL_SECONDS = 300


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


MASTER_SOCIAL_LOGIN_DETAIL = (
    "Мастера входят только через VK, Яндекс или MAX. "
    "Пароль для кабинета мастера не используется."
)


def _reject_master_password_login(user: User) -> None:
    """Masters are a social-only role (owner review 1.83.0).

    Password/OTP login would bypass the binding requirement and contradict
    the «Вход и привязки» model, so every non-social entry path rejects a
    MASTER account. ADMIN (the superuser) keeps password login.
    """
    if user.role == UserRole.MASTER:
        logger.warning("Password login blocked for master: user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MASTER_SOCIAL_LOGIN_DETAIL,
        )


# ─── Login ────────────────────────────────────────────────────────────

async def login_master(email: str, password: str, db: AsyncSession) -> tuple[str, User]:
    """Email+password login for CLIENT/ADMIN; MASTER is rejected below."""
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

    _reject_master_password_login(user)

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "is_admin": user.role == UserRole.ADMIN,
        "prefer_master": await master_landing_preference(db, user),
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

    # An existing MASTER must use a social binding; OTP is not a social login.
    _reject_master_password_login(user)

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "is_admin": user.role == UserRole.ADMIN,
        "prefer_master": await master_landing_preference(db, user),
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

    _reject_master_password_login(user)

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "prefer_master": await master_landing_preference(db, user),
    })
    logger.info("Клиент успешно вошёл в систему: %s", phone)
    return access_token, user


# ─── Unified Login ───────────────────────────────────────────────────

async def _create_password_account(
    identifier: str, password: str, contact_type: str, db: AsyncSession,
) -> User:
    """Create a CLIENT account for the unified-entry signup (1.81.0).

    Unverified by design («неверифицированные данные»): the email/phone is
    what the visitor typed, confirmed by no code — same as phone signup in
    1.80.0. Everything else is refined later in the client cabinet profile.
    Consent (152-FZ) is stamped at creation; the caller has already made
    sure it was given.
    """
    value = normalize_contact_value(contact_type, identifier)
    if await find_user_by_contact(db, contact_type, value) is not None:
        # Raced with another signup between the lookup and this point.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email/телефон или пароль",
        )
    is_email = contact_type == CONTACT_EMAIL
    new_user = User(
        name="",
        email=value if is_email else None,
        phone=None if is_email else value,
        hashed_password=hash_password(password),
        role=UserRole.CLIENT,
        consent_at=datetime.now(dt_timezone.utc),
        consent_policy_version=POLICY_VERSION,
        consent_offer_version=OFFER_VERSION,
    )
    db.add(new_user)
    await db.flush()

    # Every registrant gets a client cabinet profile.
    db.add(ClientProfile(user_id=new_user.id))

    # Typed contact, NOT verified (no code was sent) — mirrors phone signup.
    try:
        await attach_contact(
            db, new_user, contact_type, value, make_primary=True)
    except ContactTaken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот контакт уже привязан к другому аккаунту",
        )

    # Owner item 5: a brand-new client immediately gets a short how-to bell.
    from app.services.notifications import send_welcome_bell

    await send_welcome_bell(db, new_user.id)

    logger.info("Auto-registered password account: %s", value)
    return new_user


async def login_unified(
    identifier: str, password: str, db: AsyncSession, consent: bool = False,
) -> tuple[str, User, bool]:
    """Login with email OR phone + password; sign up when nothing matches.

    Unified entry (owner review 1.81.0): a first-time visitor types the
    email/phone + password they want once. If the contact is unknown, the
    backend asks for 152-FZ consent (401 + ``registration_required``) and
    creates the cabinet on the retry with ``consent=True`` — no separate
    «нет аккаунта» registration form. Returns (access_token, user, created).
    """
    logger.info("Unified login attempt: %s", identifier)

    # «Единый вход»: the identifier is a contact — email or phone. The
    # contact service owns both the new model and the legacy fallback.
    is_email = "@" in (identifier or "")
    contact_type = CONTACT_EMAIL if is_email else CONTACT_PHONE
    user = await find_user_by_contact(db, contact_type, identifier)
    created = False

    if user is None:
        # Normalize first: garbage must be a 400, not a signup attempt.
        try:
            normalize_contact_value(contact_type, identifier)
        except InvalidContact:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Введите корректный email или телефон",
            )
        # A weak password is rejected before the consent screen: the policy
        # is the same as in register_unified, but only a NEW account needs it
        # (legacy accounts keep whatever password they already have).
        try:
            validate_password_strength(password)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
            )
        if not consent:
            # 152-FZ: the cabinet is created only after explicit consent.
            # The frontend turns this code into the consent step.
            logger.info("Registration required (no consent yet): %s", identifier)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "registration_required",
                    "message": "Аккаунта с такими данными пока нет",
                },
            )
        user = await _create_password_account(
            identifier, password, contact_type, db)
        created = True

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

    _reject_master_password_login(user)

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "is_admin": user.role == UserRole.ADMIN,
        "prefer_master": await master_landing_preference(db, user),
    })

    refresh_token_value, expires_at = create_refresh_token_payload(user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_token_value, expires_at=expires_at))
    await db.commit()

    logger.info("User successfully logged in: %s", identifier)
    return access_token, user, created


async def phone_status(phone: str, db: AsyncSession) -> dict:
    """Unified entry, step 1: what awaits this phone — вход или регистрация.

    Replies "new" (no account — offer phone+password signup), "password"
    (an account with a password — ask for it) or "social" (an account
    without a password — enter via VK/Яндекс/MAX). The phone arrives
    normalized from the schema; the lookup also covers legacy accounts
    whose number still sits in users.phone.

    For "new" state, also returns a challenge token for the 2-step
    consent flow (the frontend shows the register form, then calls
    /auth/consent/complete with the challenge + consent).
    """
    user = await find_user_by_contact(db, CONTACT_PHONE, phone)
    if user is None:
        state = "new"
        # Create a challenge token for the pending registration.
        challenge = _create_challenge_token(0, phone)
    elif user.role == UserRole.MASTER:
        # Masters are social-only even if an old password still exists.
        state = "social"
        challenge = None
    elif user.hashed_password:
        state = "password"
        challenge = None
    else:
        state = "social"
        challenge = None
    logger.info("Phone status: %s -> %s", phone, state)
    result = {"state": state, "phone": phone}
    if challenge is not None:
        result["challenge"] = challenge
    return result


# ─── Unified Registration ────────────────────────────────────────────

# Legal document versions accepted at registration (consent checkbox).
# Bump together with the frontend /privacy and /offer pages.
POLICY_VERSION = "2026-10-12"
OFFER_VERSION = "2026-10-22"

async def register_unified(
    phone: str,
    password: str,
    db: AsyncSession,
    consent: bool = False,
) -> User:
    """Quick registration: phone + password, everyone a CLIENT.

    Minimal by design — name/email/address/city are refined later in the
    client cabinet profile. Becoming a master is a separate self-service
    draft (/become-master), never this path. `name` is nullable and left
    empty here; the display name is filled in once the user edits their
    profile.
    """
    logger.info("Quick registration: %s", phone)

    # 152-FZ: an account cannot be created without explicit consent. The UI
    # gates the button, but the API enforces it too (owner review 1.80.0).
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Подтвердите согласие на обработку персональных данных — "
                "без него регистрация невозможна"
            ),
        )

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

    # Owner item 5: a brand-new client immediately gets a short how-to bell.
    from app.services.notifications import send_welcome_bell

    await send_welcome_bell(db, new_user.id)

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
        "last_name": user.last_name,
        "is_admin": user.role == UserRole.ADMIN,
        "prefer_master": await master_landing_preference(db, user),
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
    """Change the password of a CLIENT or ADMIN account.

    MASTER accounts are social-only (1.83.0) and always get a 400, even if
    a legacy password hash remains. Social / OTP-only accounts have no
    password by design («пароль соц-юзерам не навязываем»): for them this
    is a 400 with a hint, never a silent password creation. Sessions stay
    alive: the user knows their new password already.
    """
    logger.info("Change password request: user_id=%s", user.id)
    if user.role == UserRole.MASTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MASTER_SOCIAL_LOGIN_DETAIL,
        )
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
    it is a deliberate user action, not an imposed password. MASTER
    accounts are social-only, so no code is sent for them.
    """
    try:
        email = normalize_email(email)
    except InvalidContact:
        return False
    user = await find_user_by_contact(db, CONTACT_EMAIL, email)
    if user is None or user.is_active is False:
        logger.info("Password reset for unknown/inactive email: %s", email)
        return False
    if user.role == UserRole.MASTER:
        # Social-only role: a password reset would issue a password session
        # and silently undo the policy. Keep the generic external response.
        logger.info("Password reset skipped for master: %s", email)
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
    if user.role == UserRole.MASTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=MASTER_SOCIAL_LOGIN_DETAIL,
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


# ─── Challenge Token (2-step consent flow, 152-FZ) ───────────────────

def _create_challenge_token(user_id: int, phone: str) -> str:
    """Create a signed JWT challenge for the 2-step consent flow.

    Used by /phone/status (new accounts) and OAuth verify endpoints
    (deferred creation) — the frontend shows ConsentScreen, then calls
    /auth/consent/complete with this token.
    """
    payload = {
        "sub": str(user_id),  # 0 for pending accounts (phone/status)
        "phone": phone,
        "iat": datetime.now(dt_timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_challenge_token(token: str) -> dict:
    """Decode and validate a challenge token. Returns payload or raises 400."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=400,
            detail="Чек-бокс согласия истёк. Начните вход заново.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=400,
            detail="Недействительный токен. Начните вход заново.",
        )
    # Validate age: max CHALLENGE_TTL_SECONDS from issued-at. PyJWT decodes
    # ``iat`` back as a numeric timestamp (not datetime) — handle both.
    issued_at = payload.get("iat")
    if issued_at is not None:
        if isinstance(issued_at, datetime):
            issued = issued_at
            if issued.tzinfo is None:
                issued = issued.replace(tzinfo=dt_timezone.utc)
        else:
            issued = datetime.fromtimestamp(float(issued_at), tz=dt_timezone.utc)
        age = (datetime.now(dt_timezone.utc) - issued).total_seconds()
        if age > CHALLENGE_TTL_SECONDS:
            raise HTTPException(
                status_code=400,
                detail="Чек-бокс согласия истёк. Начните вход заново.",
            )
    return payload


def is_challenge_token(token: str) -> bool:
    """True when ``token`` is a consent challenge, not a session JWT.

    OAuth verify returns a challenge (instead of a session token) for a
    new/pending account without consent; the routers use this helper to
    tell the two apart. Challenge claims: sub + phone + iat, no role.
    """
    if not token:
        return False
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return False
    return "phone" in payload and "role" not in payload


async def commit_pending_user(
    user: User,
    db: AsyncSession,
    consent: bool = True,
) -> None:
    """Commit a deferred user (created by OAuth verify) with consent.

    Called by /auth/consent/complete when the user accepts the consent.
    Creates ClientProfile, stamps consent_at, and logs a welcome bell.
    """
    from app.services.clients import get_or_create_profile
    from app.services.notifications import send_welcome_bell

    now = datetime.now(dt_timezone.utc)
    user.consent_at = now
    user.consent_policy_version = POLICY_VERSION
    user.consent_offer_version = OFFER_VERSION

    # Create ClientProfile if missing (OAuth verify may skip it).
    await get_or_create_profile(db, user)

    # Send welcome notification.
    await send_welcome_bell(db, user.id)

    await log_action(
        db, user.id, "consent_complete", "auth", user.id,
        f"Подтверждение согласия: {consent}", level="info",
    )
    logger.info("Deferred user committed: user_id=%s consent=%s", user.id, consent)


async def complete_consent_flow(
    user: User,
    db: AsyncSession,
    consent: bool = True,
) -> tuple[str, str]:
    """Create JWT session for a user who just completed consent.

    Returns (access_token, refresh_token_value) — caller sets cookies.
    """
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
    return access_token, refresh_value

