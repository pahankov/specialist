"""Unified User model with role-based access.

Replaces separate Master and Client models with a single User table
and role-specific profile tables (MasterProfile, ClientProfile).
"""
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, Index, func, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class UserRole(str, PyEnum):
    """User roles in the system."""
    MASTER = "MASTER"
    CLIENT = "CLIENT"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index('ix_users_email', 'email', unique=True),
        Index('ix_users_phone', 'phone', unique=True),
        Index('ix_users_role', 'role'),
        Index('ix_users_max_user_id', 'max_user_id', unique=True),
        Index('ix_users_vk_user_id', 'vk_user_id', unique=True),
        Index('ix_users_yandex_user_id', 'yandex_user_id', unique=True),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=True)
    phone = Column(String(20), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)  # null for OTP-only clients
    name = Column(String(100), nullable=False)
    # Surname is entered separately at registration (editable in profile);
    # `name` keeps the full display value "Имя Фамилия".
    last_name = Column(String(100), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CLIENT)
    city_id = Column(Integer, ForeignKey("cities.id", ondelete="SET NULL"), nullable=True)
    # Which master created this user (set on ClientsPage "+ Добавить клиента").
    # Lets a master see "own" clients: booked with them OR created by them.
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)  # email verified
    # Bound MAX messenger account: after the first MAX login the sender id is
    # stored here, so subsequent /max/start pushes the code straight into the
    # dialog (no contact share needed anymore). NULLs are distinct in PG/SQLite
    # unique indexes, so unbound users never collide.
    max_user_id = Column(BigInteger, nullable=True)
    # MAX public nickname (@username) captured at binding time — support/UX
    # hint, may be absent (MAX allows no nickname).
    max_username = Column(String(64), nullable=True)
    # Bound VK ID account: after the first VK login the VK user id is stored
    # here, so subsequent logins match the account directly (no phone/email
    # needed). Same NULL-distinct unique-index trick as max_user_id.
    vk_user_id = Column(BigInteger, nullable=True)
    # Bound Yandex ID account: after the first Yandex login the Yandex user id
    # is stored here, so subsequent logins match directly. Same NULL-distinct
    # unique-index trick as max_user_id/vk_user_id.
    yandex_user_id = Column(BigInteger, nullable=True)
    # Social avatar (a URL on the provider's CDN): filled/refreshed by social
    # logins for the client cabinet. Masters keep using master_profiles.avatar_
    # url (uploaded photo / preset) — this column is the CLIENT-facing photo.
    avatar_url = Column(String(500), nullable=True)
    # Where the display `name` came from: NULL (unset / set by a human before
    # this column existed), "user" (manually edited in the cabinet), or a
    # social provider id ("vk"/"yandex"/"max"). Social logins only fill/refresh
    # the name when it is empty or was itself set by a social login — a name
    # a human entered is never overwritten.
    name_source = Column(String(16), nullable=True)
    # Legal consent proof (152-ФЗ + offer): stamped at registration when the
    # user checks the consent box. NULL = registered before consent tracking
    # (e.g. OTP/MAX auto-created accounts) — consent unknown.
    consent_at = Column(DateTime(timezone=True), nullable=True)
    consent_policy_version = Column(String(20), nullable=True)
    consent_offer_version = Column(String(20), nullable=True)
    # Self-service soft delete: account deactivated + PII anonymized, rows kept
    # for the 3-year retention promised in /privacy, then purged. NULL = active.
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    master_profile = relationship("MasterProfile", back_populates="user", uselist=False)
    client_profile = relationship("ClientProfile", back_populates="user", uselist=False)
    # Multi-contact model (1.79.0): phones/emails with per-contact verify flags.
    contacts = relationship("UserContact", back_populates="user",
                            cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

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
