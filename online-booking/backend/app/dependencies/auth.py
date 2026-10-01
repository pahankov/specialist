"""JWT authentication dependencies for FastAPI.

Shared dependencies used across all modules:
- get_current_user      — validates JWT, returns User (any role)
- get_current_master    — validates JWT, returns User with master role
- get_current_client    — validates JWT, returns User with client role
- require_master        — requires valid master token
- require_admin         — requires admin role
- require_client        — requires valid client token
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate JWT token, return current user (any role)."""
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
    except JWTError as e:
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

    logger.debug("Authenticated user: id=%s, role=%s, name=%s", user.id, user.role, user.name)
    return user


async def get_current_master(
    credentials: HTTPAuthorizationCredentials = Depends(security),
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

    if user is None or user.master_profile is None:
        logger.error(
            "Master user found but master_profile is None: user_id=%s, role=%s",
            user.id if user else "N/A",
            user.role if user else "N/A"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Master profile not found"
        )

    logger.info("Master authenticated: id=%s, profile_id=%s", user.id, user.master_profile.id)
    return user


async def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate JWT token, return current client."""
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: int = int(payload.get("sub"))
        token_role = payload.get("role")

        if user_id is None or token_role != "CLIENT":
            logger.warning(
                "Client auth failed: user_id=%s, token_role=%s (expected CLIENT)",
                user_id, token_role
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except JWTError as e:
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

    return user


def require_master(user: User = Depends(get_current_master)) -> User:
    """Dependency that requires a valid master token."""
    return user


def require_admin(user: User = Depends(get_current_master)) -> User:
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
