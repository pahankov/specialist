from sqlalchemy import Column, Integer, Date, Time, ForeignKey, Index, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class WorkingHour(Base):
    __tablename__ = "working_hours"
    __table_args__ = (
        Index('ix_working_hours_master_date', 'master_id', 'schedule_date', unique=True),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    master_profile = relationship("MasterProfile", back_populates="working_hours")
