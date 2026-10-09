"""Master profile — stores master-specific data separate from User."""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta, timezone
from enum import Enum
from app.database import Base


class MasterStatus(str, Enum):
    """Master availability status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class MasterProfile(Base):
    __tablename__ = "master_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    description = Column(Text)
    avatar_url = Column(String(500))
    telegram_username = Column(String(100))
    experience_years = Column(Integer, nullable=True)
    status = Column(String(20), default="active", nullable=False)  # 'active', 'inactive', 'suspended'
    is_active = Column(Boolean, default=True)  # soft-delete flag
    # Billing foundation (no charges yet): every master sits on a tariff.
    # Default 'trial' with trial_ends_at assigned at creation (+180 days).
    tariff = Column(String(20), default="trial", nullable=False)
    trial_ends_at = Column(
        DateTime(timezone=True), nullable=True,
        default=lambda: datetime.now(timezone.utc) + timedelta(days=180),
    )
    # Daily work window (whole hours): schedule granules render for
    # [work_start_hour, work_end_hour). Defaults 08:00-22:00.
    work_start_hour = Column(Integer, default=8, nullable=False)
    work_end_hour = Column(Integer, default=22, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="master_profile")
    services = relationship("Service", back_populates="master_profile")
    appointments = relationship("Appointment", back_populates="master_profile")
    working_hours = relationship("WorkingHour", back_populates="master_profile")
    blocked_slots = relationship("BlockedSlot", back_populates="master_profile")
    reviews = relationship("Review", back_populates="master_profile")

    def __repr__(self):
        return f"<MasterProfile(user_id={self.user_id})>"
