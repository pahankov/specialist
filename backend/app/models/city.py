from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Index
from app.database import Base


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (
        Index('ix_cities_country_slug', 'country_id', 'slug', unique=True),
    )

    id = Column(Integer, primary_key=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    name_ru = Column(String(200), nullable=False)
    name_en = Column(String(200), nullable=True)
    slug = Column(String(200), nullable=False)  # unique within country, e.g. "moscow"
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<City(id={self.id}, name_ru={self.name_ru}, country_id={self.country_id})>"
