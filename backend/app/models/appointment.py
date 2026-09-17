from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index('ix_appointments_master_status', 'master_id', 'status'),
        Index('ix_appointments_master_date', 'master_id', 'appointment_date'),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    appointment_date = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    master = relationship("Master", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    client = relationship("Client", back_populates="appointments")
