"""Email codes — six-digit codes sent to an address (1.79.0).

Used for the password reset («Забыли пароль» → код на почту) and for
confirming a new email in the cabinet. One row per issued code:
single-use, TTL-bound, locks out after several wrong entries. The plain
code never reaches the database — only its sha256 (hash_otp_code).
"""
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String
from datetime import datetime, timezone

from app.database import Base


class EmailCode(Base):
    __tablename__ = "email_codes"
    __table_args__ = (
        Index("ix_email_codes_email_purpose", "email", "purpose"),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, index=True)
    purpose = Column(String(20), nullable=False)  # reset_password | confirm_email
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, nullable=False, default=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(timezone.utc))
