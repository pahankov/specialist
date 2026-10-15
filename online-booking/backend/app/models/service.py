from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Boolean, Text, Index, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        Index('ix_services_master_active', 'master_id', 'is_active'),
        Index('ix_services_category', 'category'),
    )

    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    # Service category for client-side grouping (e.g. "Ногти", "Шугаринг", "Ресницы").
    category = Column(String(50), nullable=True)
    description = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    # Percentage discount 0-90 (0 = none). Clients always pay the
    # effective price; the full price shows struck through.
    discount_percent = Column(Integer, nullable=True, default=0)
    # Optional expiry (naive UTC): after it the discount silently stops.
    discount_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    master_profile = relationship("MasterProfile", back_populates="services")
    appointments = relationship("Appointment", back_populates="service")

    @property
    def effective_price(self) -> float:
        from app.services.pricing import apply_discount
        return apply_discount(self.price, self.discount_percent,
                              self.discount_until)
