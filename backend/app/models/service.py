from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Boolean, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base

class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        Index('ix_services_master_active', 'master_id', 'is_active'),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)
    master = relationship("Master", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")
