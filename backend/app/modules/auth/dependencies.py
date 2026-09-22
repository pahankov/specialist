"""JWT authentication dependencies for FastAPI.

Updated to use the unified User model with role-based access.

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

from app.database import get_db
from app.models.user import User, UserRole
from app.config import settings

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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


async def get_current_master(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Extract and validate JWT token, return current master."""
    user = await get_current_user(credentials, db)

    if user.role not in (UserRole.MASTER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token — not a master"
        )

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

        if user_id is None or token_role != "client":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешён только администраторам"
        )
    return user


# Backward compatibility alias
require_super_admin = require_admin


def require_client(user: User = Depends(get_current_client)) -> User:
    """Dependency that requires a valid client token."""
    return user
