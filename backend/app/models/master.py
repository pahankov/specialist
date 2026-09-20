from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Master(Base):
    __tablename__ = "masters"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    phone = Column(String(20))
    telegram_username = Column(String(100))
    description = Column(Text)
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    services = relationship("Service", back_populates="master")
    appointments = relationship("Appointment", back_populates="master")
    working_hours = relationship("WorkingHour", back_populates="master")
    audit_logs = relationship("AuditLog", back_populates="master")
    blocked_slots = relationship("BlockedSlot", back_populates="master")
