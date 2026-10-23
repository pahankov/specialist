"""Per-user notification delivery preferences."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String

from app.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    instant_enabled = Column(Boolean, nullable=False, default=True)
    reminders_enabled = Column(Boolean, nullable=False, default=True)
    max_enabled = Column(Boolean, nullable=False, default=True)
    vk_enabled = Column(Boolean, nullable=False, default=True)
    email_enabled = Column(Boolean, nullable=False, default=True)
    preferred_channel = Column(String(16), nullable=False, default="auto")
    master_digest_enabled = Column(Boolean, nullable=False, default=True)
    digest_lead_minutes = Column(Integer, nullable=False, default=60)
    last_digest_on = Column(Date, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
