"""JWT authentication dependencies for FastAPI.

Shared dependencies used across all modules:
- get_current_user      — validates JWT, returns User (any role)
- get_current_master    — validates JWT, returns User with master role
- get_current_client    — validates JWT, returns User with client role
- require_master        — requires valid master token
- require_admin         — requires admin role
- require_client        — requires valid client token
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# auto_error=False: a missing access cookie must be a 401, not HTTPBearer's
# default 403. The frontend refreshes the session on 401; a 403 bypasses that
# flow and leaves an otherwise valid refresh session stuck.
security = HTTPBearer(auto_error=False)
security_optional = HTTPBearer(auto_error=False)


def _missing_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user, but None instead of 401 without a token.

    Used by endpoints that work anonymously but behave differently for a
    signed-in user (e.g. social «Привязать» start calls).
    """
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id = int(payload.get("sub"))
    except (jwt.PyJWTError, TypeError, ValueError):
        return None
    user = (await db.execute(
        select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or user.is_active is False:
        return None
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate JWT token, return current user (any role)."""
    if credentials is None:
        logger.warning("Authentication failed: missing access token")
        raise _missing_credentials()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: int = int(payload.get("sub"))
        if user_id is None:
            logger.warning("JWT valid payload but missing 'sub' field")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        token_role = payload.get("role")
        logger.debug("JWT decoded: user_id=%s, role=%s", user_id, token_role)
    except jwt.PyJWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("User not found in DB: user_id=%s (from JWT)", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user.is_active is False:
        logger.warning("Deactivated user from JWT: user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Аккаунт удалён"
        )

    logger.debug("Authenticated user: id=%s, role=%s, name=%s", user.id, user.role, user.name)
    return user


async def get_current_master(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate JWT token, return current master.
    
    Uses joinedload to eagerly load master_profile, preventing
    MissingGreenlet errors when accessing master.master_profile.id
    in async endpoints.
    """
    user = await get_current_user(credentials, db)

    if user.role not in (UserRole.MASTER, UserRole.ADMIN):
        logger.warning(
            "Access denied: user_id=%s has role=%s, expected MASTER or ADMIN",
            user.id, user.role
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token — not a master"
        )

    # Eagerly load master_profile to avoid lazy-load in async context
    result = await db.execute(
        select(User)
        .options(joinedload(User.master_profile))
        .where(User.id == user.id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.error(
            "Master user not found: role=%s",
            user.role if user else "N/A"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Master profile not found"
        )

    # Admin users (role=ADMIN) don't have MasterProfile — that's expected
    if user.role == UserRole.MASTER and user.master_profile is None:
        logger.error(
            "Master user found but master_profile is None: user_id=%s",
            user.id
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Master profile not found"
        )

    # Unverified applicants, deactivated and suspended masters stay out
    # of the panel (client cabinet remains available — dual-role).
    # NOTE: status "inactive" alone does NOT block: it is also the
    # automatic state of masters with no future working hours, who must
    # still open the panel (e.g. to add hours). Only explicit admin
    # states count: is_active=False (toggle/applicant) or "suspended".
    if user.role == UserRole.MASTER and user.master_profile is not None:
        _mp = user.master_profile
        if _mp.is_active is False or _mp.status == "suspended":
            logger.warning("Inactive master panel access denied: user_id=%s",
                           user.id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Профиль мастера неактивен"
            )

    if user.master_profile is not None:
        # Billing gate: unpaid invoices freeze mutations, never reads.
        # The background billing tick owns the status; this check is a
        # cheap read so a stale token cannot write after the due date.
        path = request.url.path
        inbox_action = (
            "/notifications" in path
            and (
                (request.method == "POST"
                 and (path.endswith("/read") or path.endswith("/notifications/read-all")))
                or (request.method == "DELETE" and path.endswith("/notifications"))
            )
        )
        if (user.role == UserRole.MASTER
                and request.method not in ("GET", "HEAD", "OPTIONS")
                and not inbox_action
                and not path.endswith("/logout")):
            from app.models.billing import MasterBillingAccount
            access = (await db.execute(
                select(MasterBillingAccount.access_status).where(
                    MasterBillingAccount.master_id == user.master_profile.id)
            )).scalar_one_or_none()
            if access in ("readonly", "paused", "suspended"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=("Кабинет работает только для чтения: счёт не оплачен. "
                            "Оплатите счёт в разделе «Тариф и оплата»."),
                )
        logger.info("Master authenticated: id=%s, profile_id=%s", user.id, user.master_profile.id)
    else:
        logger.info("Admin authenticated (no master_profile): id=%s", user.id)
    return user


async def get_current_client(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate JWT token, return current client.

    Dual-role: MASTER users are welcome too (a master can book other
    masters as a client). Their ClientProfile is created on first visit
    by the callers (services.clients.get_or_create_profile).
    """
    if credentials is None:
        logger.warning("Client authentication failed: missing access token")
        raise _missing_credentials()
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: int = int(payload.get("sub"))
        token_role = payload.get("role")

        if user_id is None or token_role not in ("CLIENT", "MASTER"):
            logger.warning(
                "Client auth failed: user_id=%s, token_role=%s (expected CLIENT or MASTER)",
                user_id, token_role
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except jwt.PyJWTError as e:
        logger.warning("JWT validation failed for client: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("Client user not found: user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if user.is_active is False:
        logger.warning("Deactivated client from JWT: user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Аккаунт удалён"
        )

    return user


def require_master(user: User = Depends(get_current_master)) -> User:
    """Dependency that requires a valid master token."""
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires an admin user."""
    if user.role != UserRole.ADMIN:
        logger.warning(
            "Admin access denied: user_id=%s, role=%s",
            user.id, user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешён только администраторам"
        )
    logger.info("Admin authenticated: user_id=%s, name=%s", user.id, user.name)
    return user


# Backward compatibility alias
require_super_admin = require_admin


def require_client(user: User = Depends(get_current_client)) -> User:
    """Dependency that requires a valid client token."""
    return user
