"""Personal coupons: master issues a code to own clients (-% or -RUB).

Booked via the cabinet promo field; the discount applies on top of the
effective price and is snapshotted on the appointment.
"""
from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    # Uppercase latin/digits, unique per master (clients type it by hand).
    code = Column(String(24), nullable=False)
    # 'percent' (1-90) or 'fixed' (RUB off, capped by the price).
    kind = Column(String(10), nullable=False, default="percent")
    value = Column(Numeric(10, 2), nullable=False, default=0)
    max_uses = Column(Integer, nullable=True)
    used_count = Column(Integer, nullable=False, default=0)
    # Audience: NULL = all own clients, else JSON user ids (own only).
    user_ids = Column(JSON, nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    master_profile = relationship("MasterProfile")
    uses = relationship("CouponUse", back_populates="coupon",
                        cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Coupon(id={self.id} code={self.code!r})>"


class CouponUse(Base):
    __tablename__ = "coupon_uses"

    id = Column(Integer, primary_key=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="SET NULL"),
                            nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"),
                     nullable=True)
    amount = Column(Numeric(10, 2), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    coupon = relationship("Coupon", back_populates="uses")
