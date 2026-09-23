from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    appointment_id = Column(
        Integer, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    master_id = Column(Integer, ForeignKey("masters.id", ondelete="CASCADE"), nullable=False, index=True)
    client_name = Column(String(100), nullable=False)
    client_phone = Column(String(20), nullable=False)
    rating = Column(Float, nullable=False)  # 1.0 — 5.0
    comment = Column(Text)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    appointment = relationship("Appointment", back_populates="reviews")
    master = relationship("Master", back_populates="reviews")

    __table_args__ = (
        Index("ix_reviews_master_published", "master_id", "is_published"),
    )
