from sqlalchemy import Column, Integer, String, Time, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base

class WorkingHour(Base):
    __tablename__ = "working_hours"
    __table_args__ = (
        Index('ix_working_hours_master_dow', 'master_id', 'day_of_week', unique=True),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    master = relationship("Master", back_populates="working_hours")