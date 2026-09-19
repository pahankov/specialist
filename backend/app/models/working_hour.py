from sqlalchemy import Column, Integer, String, Time, ForeignKey, Index, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class WorkingHour(Base):
    __tablename__ = "working_hours"
    __table_args__ = (
        Index('ix_working_hours_master_date', 'master_id', 'schedule_date', unique=True),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)
    schedule_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    master = relationship("Master", back_populates="working_hours")
