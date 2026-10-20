"""Master profile — stores master-specific data separate from User."""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Index, JSON
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
    # Preset avatar (emoji id like "cat"): mutually exclusive with avatar_url.
    avatar_preset = Column(String(12), nullable=True)
    telegram_username = Column(String(100))
    experience_years = Column(Integer, nullable=True)
    status = Column(String(20), default="active", nullable=False)  # 'active', 'inactive', 'suspended'
    is_active = Column(Boolean, default=True)  # soft-delete flag
    # Client-initiated bookings (cabinet wizard, public form) land as
    # "confirmed" instead of "pending". Master toggles it in profile.
    auto_confirm = Column(Boolean, default=False, nullable=False)
    # Past confirmed bookings flip to "completed" on their own (background
    # loop). Manual complete/cancel still work — the switch only automates.
    auto_complete = Column(Boolean, default=False, nullable=True)
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
    # Cabinet address (free text, picked via DaData suggest on the client).
    cabinet_address = Column(String(500), nullable=True)
    # Certificates: [{name, url?}] — editable by the master in profile.
    certificates = Column(JSON, nullable=False, default=list)
    # Login landing (1.82.0): a master goes straight to the panel after
    # login. Unchecked in the application/profile → the client cabinet.
    prefer_master_cabinet = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="master_profile")
    services = relationship("Service", back_populates="master_profile")
    bundles = relationship("ServiceBundle", back_populates="master_profile",
                           cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="master_profile")
    working_hours = relationship("WorkingHour", back_populates="master_profile")
    blocked_slots = relationship("BlockedSlot", back_populates="master_profile")
    reviews = relationship("Review", back_populates="master_profile")

    def __repr__(self):
        return f"<MasterProfile(user_id={self.user_id})>"
