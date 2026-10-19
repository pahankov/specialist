"""User contacts: multiple phones/emails per account with verify flags.

Part of the 1.79.0 "Единый вход" package (см. LOCAL.md): the unified login
entry searches accounts by contact value, so phones/emails stop being scalar
columns and become rows with their own state:

- contact_type: "phone" | "email";
- value: normalized uniformly — phones via app.utils.phone.normalize_phone
  ("+7 (XXX) XXX-XX-XX"), emails lowercased. The unique index below relies on
  every writer using exactly these formats.
- verification levels (agreed): не подтверждён (is_verified=False) /
  подтверждён соцвходом (verified_via="social") / подтверждён кодом на
  контакт (verified_via="code", только почта). Телефон подтверждается только
  соцвходом; парольные аккаунты остаются без верификаций.
- is_primary: the contact preferred in the UI; "exactly one per (user, type)"
  is maintained by the service layer, not by a DB constraint.

users.phone / users.email stay during the transition; migration 24a1b2c3d4e9
backfills this table from them.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.database import Base


class UserContact(Base):
    __tablename__ = "user_contacts"
    __table_args__ = (
        Index("ix_user_contacts_user_id", "user_id"),
        # A value lives on exactly one account: the login flows resolve
        # collisions explicitly (transfer + audit log), never via DB magic.
        Index("ix_user_contacts_type_value", "contact_type", "value",
              unique=True),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False)
    contact_type = Column(String(10), nullable=False)  # "phone" | "email"
    value = Column(String(255), nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    # "social" | "code" | NULL (не подтверждён)
    verified_via = Column(String(16), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="contacts")

    def __repr__(self):
        return (f"<UserContact(id={self.id}, user_id={self.user_id}, "
                f"type={self.contact_type}, value={self.value})>")
