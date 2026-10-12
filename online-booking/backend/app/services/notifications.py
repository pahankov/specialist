"""Internal bell writer shared by admin / client / public flows."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.logging_config import get_logger

logger = get_logger(__name__)


async def notify_user(
    db: AsyncSession,
    recipient_id: int,
    text: str,
    sender_id: Optional[int] = None,
    audience: str = "system",
    link: Optional[str] = None,
) -> Notification:
    """Write one inbox row (flush only — caller commits)."""
    note = Notification(
        sender_id=sender_id,
        recipient_id=recipient_id,
        text=text.strip(),
        audience=audience,
        link=link,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    await db.flush()
    logger.info("Bell: to=%s audience=%s link=%s", recipient_id, audience, link)
    return note
