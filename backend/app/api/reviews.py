"""Public reviews API — no auth required."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.database import get_db
from app.models.review import Review
from app.models.appointment import Appointment
from app.schemas.review import ReviewResponse, ReviewCreate, ReviewUpdate
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=List[ReviewResponse])
async def get_reviews(
    master_id: Optional[int] = Query(None),
    only_published: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get reviews. Public: only published. Masters can see their own unpublished."""
    query = select(Review)

    if master_id is not None:
        query = query.where(Review.master_id == master_id)

    if only_published:
        query = query.where(Review.is_published == True)  # noqa: E712

    query = query.order_by(Review.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/average", response_model=dict)
async def get_average_rating(
    master_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get average rating for a master (published only)."""
    result = await db.execute(
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("count")
        ).where(Review.master_id == master_id, Review.is_published == True)  # noqa: E712
    )
    row = result.one()
    avg = round(float(row.avg_rating), 1) if row.avg_rating else None
    return {"average_rating": avg, "review_count": row.count}


@router.post("/", response_model=ReviewResponse, status_code=201)
async def create_review(
    review_data: ReviewCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a review for a completed appointment."""
    # Verify appointment exists and is completed
    result = await db.execute(
        select(Appointment)
        .where(Appointment.id == review_data.appointment_id)
        .options(selectinload(Appointment.client))
    )
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.status != "completed":
        raise HTTPException(status_code=400, detail="Can only review completed appointments")

    # Check if review already exists
    existing = await db.execute(
        select(Review).where(Review.appointment_id == review_data.appointment_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Review already exists for this appointment")

    new_review = Review(
        appointment_id=review_data.appointment_id,
        master_id=appointment.master_id,
        client_name="Client",
        client_phone="",
        rating=review_data.rating,
        comment=review_data.comment,
        is_published=True,
    )

    # Enrich with client info from appointment
    if appointment.client:
        new_review.client_name = appointment.client.name or "Client"
        new_review.client_phone = appointment.client.phone or ""

    db.add(new_review)
    await db.commit()
    await db.refresh(new_review)
    return new_review


@router.patch("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int,
    review_data: ReviewUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a review (publish/unpublish, edit comment)."""
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review_data.comment is not None:
        review.comment = review_data.comment
    if review_data.is_published is not None:
        review.is_published = review_data.is_published

    await db.commit()
    await db.refresh(review)
    return review


@router.delete("/{review_id}", status_code=204)
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a review."""
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await db.delete(review)
    await db.commit()
    return None
