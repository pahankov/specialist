"""Client profile — stores client-specific data separate from User."""
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    no_show_count = Column(Integer, default=0)
    preferred_service_ids = Column(JSON, nullable=True)  # list of service IDs
    # Client location (free text, picked via DaData suggest on the client).
    # City for matching still lives on users.city_id (parsed at write time).
    address = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="client_profile")
    appointments = relationship("Appointment", back_populates="client_profile")

    def __repr__(self):
        return f"<ClientProfile(user_id={self.user_id})>"
