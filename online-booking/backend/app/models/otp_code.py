"""OTP code model for phone-based authentication."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class OtpCode(Base):
    __tablename__ = "otp_codes"
    __table_args__ = (
        Index('ix_otp_codes_phone', 'phone'),
        Index('ix_otp_codes_code_hash', 'code_hash'),
        Index('ix_otp_codes_channel', 'channel'),
    )

    id = Column(Integer, primary_key=True)
    phone = Column(String(20), nullable=False)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Auth channel: 'sms' (code typed on site) or 'max' (code delivered to MAX dialog).
    # For 'max', max_user_id being set means the bot delivered a code for the
    # request (is_used flips only when the site session is issued via /max/verify).
    channel = Column(String(10), nullable=False, default="sms")
    max_user_id = Column(BigInteger, nullable=True)
    max_user_name = Column(String(200), nullable=True)
    # True when the dialog number came from a request_contact share whose
    # HMAC matched (proven MAX-bound number -> user created verified).
    max_verified_phone = Column(Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<OtpCode(phone={self.phone}, used={self.is_used})>"
