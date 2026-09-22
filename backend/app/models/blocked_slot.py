from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class BlockedSlot(Base):
    __tablename__ = "blocked_slots"
    __table_args__ = (
        Index('ix_blocked_slots_master', 'master_id', 'start_dt'),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    start_dt = Column(DateTime, nullable=False)
    end_dt = Column(DateTime, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    master_profile = relationship("MasterProfile", back_populates="blocked_slots")

    def __repr__(self):
        return f"<BlockedSlot {self.start_dt} - {self.end_dt}>"
