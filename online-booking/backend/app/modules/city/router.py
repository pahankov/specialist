"""City and Country API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Optional

from app.database import get_db
from app.models.country import Country
from app.models.city import City
from app.schemas.country import CountryResponse, CountryCreate, CountryUpdate
from app.schemas.city import CityResponse, CityCreate, CityUpdate
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ─── Countries ────────────────────────────────────────────────────────

@router.get("/countries/", response_model=List[CountryResponse])
async def get_countries(
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(True, description="Return only active countries"),
):
    """Get all countries."""
    query = select(Country)
    if active_only:
        query = query.where(Country.is_active == True)
    query = query.order_by(Country.name_ru)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/countries/{country_id}", response_model=CountryResponse)
async def get_country(country_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single country by ID."""
    result = await db.execute(select(Country).where(Country.id == country_id))
    country = result.scalar_one_or_none()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


# ─── Cities ───────────────────────────────────────────────────────────

@router.get("/cities/", response_model=List[CityResponse])
async def get_cities(
    db: AsyncSession = Depends(get_db),
    country_id: Optional[int] = Query(None, description="Filter by country ID"),
    search: Optional[str] = Query(None, description="Search cities by name (Russian)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    active_only: bool = Query(True, description="Return only active cities"),
):
    """Get cities with pagination, optional country filter and search."""
    query = select(City)
    if country_id is not None:
        query = query.where(City.country_id == country_id)
    if search:
        search_pattern = f"%{search.lower()}%"
        query = query.where(func.lower(City.name_ru).like(search_pattern))
    if active_only:
        query = query.where(City.is_active == True)
    query = query.order_by(City.name_ru)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    cities = result.scalars().all()

    return cities


@router.get("/cities/search/", response_model=List[CityResponse])
async def search_cities(
    q: str = Query(..., min_length=1, description="Search query"),
    country_id: Optional[int] = Query(None, description="Filter by country ID"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
):
    """Search cities by name with optional country filter."""
    query = select(City).where(func.lower(City.name_ru).like(f"%{q.lower()}%"))
    if country_id is not None:
        query = query.where(City.country_id == country_id)
    query = query.where(City.is_active == True)
    query = query.order_by(City.name_ru).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/cities/{city_id}", response_model=CityResponse)
async def get_city(city_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single city by ID."""
    result = await db.execute(select(City).where(City.id == city_id))
    city = result.scalar_one_or_none()
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    return city
