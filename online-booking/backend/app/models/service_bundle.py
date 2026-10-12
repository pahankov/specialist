"""Service bundle (complex) — a named set of the master's own services.

Booked as ONE appointment: durations sum up, price is custom or the sum.
Kept separate from services (own list, own CRUD, own booking flow).
"""
from sqlalchemy import Column, Integer, String, Numeric, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class ServiceBundle(Base):
    __tablename__ = "service_bundles"

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    name = Column(String(200), nullable=False)
    # Ordered service ids (validated: own + existing at write time).
    service_ids = Column(JSON, nullable=False, default=list)
    # Per-service duration overrides inside the complex: {service_id: minutes}.
    # Missing key = the service's own duration.
    durations = Column(JSON, nullable=True)
    # Custom price; NULL = sum of services at booking time.
    price = Column(Numeric(10, 2), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    master_profile = relationship("MasterProfile", back_populates="bundles")
    appointments = relationship("Appointment", back_populates="bundle")

    def __repr__(self):
        return f"<ServiceBundle(id={self.id} name={self.name!r})>"
