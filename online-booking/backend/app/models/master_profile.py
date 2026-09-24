"""Master profile — stores master-specific data separate from User."""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Index, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
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
    status = Column(SAEnum(MasterStatus), default=MasterStatus.ACTIVE, nullable=False)
    is_active = Column(Boolean, default=True)  # soft-delete flag
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="master_profile")
    services = relationship("Service", back_populates="master_profile")
    appointments = relationship("Appointment", back_populates="master_profile")
    working_hours = relationship("WorkingHour", back_populates="master_profile")
    audit_logs = relationship("AuditLog", back_populates="master_profile")
    blocked_slots = relationship("BlockedSlot", back_populates="master_profile")
    reviews = relationship("Review", back_populates="master_profile")

    def __repr__(self):
        return f"<MasterProfile(user_id={self.user_id})>"
