from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index('ix_clients_phone', 'phone', unique=True),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(255), index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    appointments = relationship("Appointment", back_populates="client")
