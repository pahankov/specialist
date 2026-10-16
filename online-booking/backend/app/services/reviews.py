"""Review serialization (services layer, no router deps).

Canonical home for the review dict shape shared by the public review
router and the client cabinet. Both import from here (modules -> services).
"""
from app.models.review import Review


def review_to_dict(r: Review) -> dict:
    return {
        "id": r.id,
        "appointment_id": r.appointment_id,
        "master_id": r.master_id,
        "client_name": r.client_name,
        "client_phone": r.client_phone,
        "rating": r.rating,
        "comment": r.comment,
        "is_published": r.is_published,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
