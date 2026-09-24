"""OTP code model for phone-based authentication."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class OtpCode(Base):
    __tablename__ = "otp_codes"
    __table_args__ = (
        Index('ix_otp_codes_phone', 'phone'),
        Index('ix_otp_codes_code_hash', 'code_hash'),
    )

    id = Column(Integer, primary_key=True)
    phone = Column(String(20), nullable=False)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<OtpCode(phone={self.phone}, used={self.is_used})>"
