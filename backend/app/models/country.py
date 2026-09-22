from sqlalchemy import Column, Integer, String, Boolean, Index
from app.database import Base


class Country(Base):
    __tablename__ = "countries"
    __table_args__ = (
        Index('ix_countries_code', 'code', unique=True),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(3), nullable=False, unique=True)  # ISO 3166-1 alpha-2
    name_ru = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    phone_prefix = Column(String(10), nullable=False)  # e.g. "+7"
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Country(code={self.code}, name_ru={self.name_ru})>"
