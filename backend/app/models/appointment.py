from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index
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
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("client_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_date = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    master_profile = relationship("MasterProfile", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    client_profile = relationship("ClientProfile", back_populates="appointments")
    reviews = relationship("Review", back_populates="appointment")
