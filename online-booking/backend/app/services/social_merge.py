"""Smart merge of social profile data into a User (VK / Yandex / MAX).

Policy (agreed): fill what is empty, never lose what a human set.
- name / last_name: taken from the social login when the name is EMPTY or was
  itself set by a social login (name_source is a provider id). A name a human
  entered — in the cabinet or by an admin — carries name_source "user"/NULL
  and is NEVER overwritten, so switching providers never clobbers a curated
  name (and a legacy NULL name_source is treated as human-set for safety).
- email: filled only when empty AND not already owned by another account —
  social logins never re-point an email onto a different (unique) row.
- avatar_url: refreshed by the latest social login that carries one.
- is_verified: monotonic — only ever upgraded, never downgraded.

Returns True when anything changed (the caller decides to commit).
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.names import compose_full_name

# name_source values that mean "a social login set this name" — any of them
# may be refreshed by a later social login. Anything else ("user"/NULL) is a
# human-set name and is left alone.
SOCIAL_NAME_SOURCES = ("vk", "yandex", "max")


async def merge_social_profile(
    db: AsyncSession,
    user: User,
    *,
    provider: str,
    first_name: str = "",
    last_name: str = "",
    email: Optional[str] = None,
    avatar_url: Optional[str] = None,
    verified: bool = False,
) -> bool:
    """Apply the smart-merge policy for one social login. Returns changed."""
    changed = False

    # ── name / last_name ────────────────────────────────────────────────
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    social_name = compose_full_name(first, last) if (first or last) else ""
    may_set_name = not user.name or user.name_source in SOCIAL_NAME_SOURCES
    if social_name and may_set_name:
        if social_name != user.name or (last or None) != user.last_name:
            user.name = social_name
            user.last_name = last or None
            user.name_source = provider
            changed = True

    # ── email (fill-if-empty, never steal a taken address) ──────────────
    if email and not user.email:
        taken = (await db.execute(
            select(User.id).where(User.email == email, User.id != user.id)
        )).scalar_one_or_none()
        if taken is None:
            user.email = email
            changed = True

    # ── avatar (latest social login that has one wins) ──────────────────
    if avatar_url and user.avatar_url != avatar_url:
        user.avatar_url = avatar_url
        changed = True

    # ── is_verified (only ever goes up) ─────────────────────────────────
    if verified and not user.is_verified:
        user.is_verified = True
        changed = True

    return changed
