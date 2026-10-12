from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index('ix_appointments_master_status', 'master_id', 'status'),
        Index('ix_appointments_master_date', 'master_id', 'appointment_date'),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    # NULL for bundle bookings (bundle snapshots below carry the facts).
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("client_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    # Bundle booking: one appointment per complex (SET NULL on bundle delete,
    # snapshots keep history readable).
    bundle_id = Column(Integer, ForeignKey("service_bundles.id", ondelete="SET NULL"),
                       nullable=True, index=True)
    bundle_name = Column(String(200), nullable=True)
    # Snapshots at booking time (bundles only; service flow uses live joins).
    duration_minutes = Column(Integer, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    appointment_date = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    master_profile = relationship("MasterProfile", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    bundle = relationship("ServiceBundle", back_populates="appointments")
    client_profile = relationship("ClientProfile", back_populates="appointments")
    reviews = relationship("Review", back_populates="appointment")
