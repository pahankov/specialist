"""Unified User model with role-based access.

Replaces separate Master and Client models with a single User table
and role-specific profile tables (MasterProfile, ClientProfile).
"""
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, Index, func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class UserRole(str, PyEnum):
    """User roles in the system."""
    MASTER = "master"
    CLIENT = "client"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index('ix_users_email', 'email', unique=True),
        Index('ix_users_phone', 'phone', unique=True),
        Index('ix_users_role', 'role'),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=True)  # null for OTP-only clients
    name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CLIENT)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # email verified
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    master_profile = relationship("MasterProfile", back_populates="user", uselist=False)
    client_profile = relationship("ClientProfile", back_populates="user", uselist=False)
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role.value})>"

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_master(self) -> bool:
        return self.role == UserRole.MASTER

    @property
    def is_client(self) -> bool:
        return self.role == UserRole.CLIENT
