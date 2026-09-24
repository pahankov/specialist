"""Admin review management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.database import get_db
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewResponse
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_super_admin
from app.services.audit import log_action

router = APIRouter()


@router.get("/reviews", response_model=PaginatedResponse[ReviewResponse])
async def get_admin_reviews(
    super_admin: User = Depends(require_super_admin),
    master_id: Optional[int] = Query(None, description="Filter by master ID"),
    is_published: Optional[bool] = Query(None, description="Filter by published status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db)
):
    """Get all reviews (superadmin only).
    
    Supports filtering by master_id and published status.
    """
    offset = (page - 1) * page_size

    # Build base query
    base_query = select(Review)
    count_query = select(func.count(Review.id))

    if master_id is not None:
        base_query = base_query.where(Review.master_id == master_id)
        count_query = count_query.where(Review.master_id == master_id)

    if is_published is not None:
        base_query = base_query.where(Review.is_published == is_published)
        count_query = count_query.where(Review.is_published == is_published)

    # Get total
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get data
    data_query = (
        base_query
        .options(selectinload(Review.master_profile))
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_query)
    reviews = result.scalars().all()

    items = [
        ReviewResponse(
            id=r.id,
            appointment_id=r.appointment_id,
            master_id=r.master_id,
            client_name=r.client_name,
            client_phone=r.client_phone,
            rating=r.rating,
            comment=r.comment,
            is_published=r.is_published,
            created_at=r.created_at,
        )
        for r in reviews
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )


@router.get("/reviews/average/{master_id}", response_model=dict)
async def get_master_average_rating(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get average rating for a specific master (superadmin only)."""
    result = await db.execute(
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("count")
        ).where(Review.master_id == master_id, Review.is_published == True)
    )
    row = result.one()
    avg = round(float(row.avg_rating), 1) if row.avg_rating else None
    return {"average_rating": avg, "review_count": row.count}


@router.patch("/reviews/{review_id}/publish", response_model=ReviewResponse)
async def publish_review(
    review_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Publish a review (superadmin only)."""
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.is_published = True
    await log_action(db, super_admin.id, "publish", "review", review_id, f"Review #{review_id} published", level="info")
    await db.commit()
    await db.refresh(review)

    return ReviewResponse(
        id=review.id,
        appointment_id=review.appointment_id,
        master_id=review.master_id,
        client_name=review.client_name,
        client_phone=review.client_phone,
        rating=review.rating,
        comment=review.comment,
        is_published=review.is_published,
        created_at=review.created_at,
    )


@router.patch("/reviews/{review_id}/unpublish", response_model=ReviewResponse)
async def unpublish_review(
    review_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unpublish a review (superadmin only)."""
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.is_published = False
    await log_action(db, super_admin.id, "unpublish", "review", review_id, f"Review #{review_id} unpublished", level="info")
    await db.commit()
    await db.refresh(review)

    return ReviewResponse(
        id=review.id,
        appointment_id=review.appointment_id,
        master_id=review.master_id,
        client_name=review.client_name,
        client_phone=review.client_phone,
        rating=review.rating,
        comment=review.comment,
        is_published=review.is_published,
        created_at=review.created_at,
    )


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review(
    review_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a review (superadmin only)."""
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    await log_action(db, super_admin.id, "delete", "review", review_id, f"Review deleted: {review.client_name}", level="warning")
    await db.delete(review)
    await db.commit()
    return None
