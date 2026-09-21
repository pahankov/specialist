"""Tests for reviews API."""
import pytest


@pytest.fixture
async def completed_appointment(session, auth_context):
    """Create a completed appointment for review."""
    from app.models.appointment import Appointment
    from app.models.service import Service
    from app.models.client import Client
    from datetime import datetime
    
    # Create a service first
    service = Service(
        master_id=auth_context["master_id"],
        name="Test Service",
        duration_minutes=60,
        price=2500,
        is_active=True,
    )
    session.add(service)
    await session.flush()
    
    # Create a client
    client = Client(name="Test Client", phone="+79001234567")
    session.add(client)
    await session.flush()
    
    appointment = Appointment(
        master_id=auth_context["master_id"],
        service_id=service.id,
        client_id=client.id,
        appointment_date=datetime(2026, 1, 1, 10, 0),
        status="completed",
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


@pytest.fixture
async def test_review(session, completed_appointment, auth_context):
    """Create a review for the completed appointment."""
    from app.models.review import Review
    
    review = Review(
        appointment_id=completed_appointment.id,
        master_id=auth_context["master_id"],
        client_name="Test Client",
        client_phone="+79001234567",
        rating=5.0,
        comment="Отличный мастер!",
        is_published=True,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


@pytest.fixture
async def unpublished_review(session, auth_context):
    """Create an unpublished review."""
    from app.models.appointment import Appointment
    from app.models.service import Service
    from app.models.client import Client
    from app.models.review import Review
    from datetime import datetime
    
    service = Service(
        master_id=auth_context["master_id"],
        name="Test Service 2",
        duration_minutes=60,
        price=2500,
        is_active=True,
    )
    session.add(service)
    await session.flush()
    
    client = Client(name="Another Client", phone="+79009876543")
    session.add(client)
    await session.flush()
    
    appointment = Appointment(
        master_id=auth_context["master_id"],
        service_id=service.id,
        client_id=client.id,
        appointment_date=datetime(2026, 1, 2, 10, 0),
        status="completed",
    )
    session.add(appointment)
    await session.flush()
    
    review = Review(
        appointment_id=appointment.id,
        master_id=auth_context["master_id"],
        client_name="Another Client",
        client_phone="+79009876543",
        rating=4.0,
        comment="Хорошо, но could быть лучше",
        is_published=False,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


# ─── Public endpoints (no auth required) ──────────────────────────

@pytest.mark.asyncio
async def test_get_reviews_public(client, auth_context, test_review):
    """Test getting published reviews without auth."""
    response = await client.get("/api/v1/reviews/", params={"master_id": auth_context["master_id"]})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == test_review.id
    assert data[0]["rating"] == 5.0
    assert data[0]["is_published"] is True


@pytest.mark.asyncio
async def test_get_reviews_only_published(client, auth_context, test_review, unpublished_review):
    """Test that only published reviews are returned by default."""
    response = await client.get("/api/v1/reviews/", params={"master_id": auth_context["master_id"]})
    assert response.status_code == 200
    data = response.json()
    assert all(r["is_published"] is True for r in data)


@pytest.mark.asyncio
async def test_get_average_rating(client, auth_context, test_review, unpublished_review):
    """Test average rating endpoint."""
    response = await client.get("/api/v1/reviews/average", params={"master_id": auth_context["master_id"]})
    assert response.status_code == 200
    data = response.json()
    assert "average_rating" in data
    assert "review_count" in data
    assert data["review_count"] >= 1


# ─── Authenticated endpoints ──────────────────────────────────────

@pytest.mark.asyncio
async def test_create_review(client, auth_context, session, completed_appointment):
    """Test creating a review for a completed appointment."""
    response = await client.post(
        "/api/v1/reviews/",
        json={
            "appointment_id": completed_appointment.id,
            "rating": 4.5,
            "comment": "Было отлично!",
        },
        headers={"Authorization": f"Bearer {auth_context['token']}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["rating"] == 4.5
    assert data["comment"] == "Было отлично!"
    assert data["is_published"] is True


@pytest.mark.asyncio
async def test_create_review_invalid_rating(client, auth_context, completed_appointment):
    """Test that ratings outside 1-5 range are rejected."""
    response = await client.post(
        "/api/v1/reviews/",
        json={"appointment_id": completed_appointment.id, "rating": 6.0},
        headers={"Authorization": f"Bearer {auth_context['token']}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_review_on_non_completed(client, auth_context, session):
    """Test that reviews can only be created for completed appointments."""
    from app.models.appointment import Appointment
    from app.models.service import Service
    from app.models.client import Client
    from datetime import datetime
    
    service = Service(
        master_id=auth_context["master_id"],
        name="Test Service Pending",
        duration_minutes=60,
        price=2500,
        is_active=True,
    )
    session.add(service)
    await session.flush()
    
    client_model = Client(name="Pending Client", phone="+79001111111")
    session.add(client_model)
    await session.flush()
    
    appointment = Appointment(
        master_id=auth_context["master_id"],
        service_id=service.id,
        client_id=client_model.id,
        appointment_date=datetime(2026, 1, 1, 10, 0),
        status="pending",
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)

    response = await client.post(
        "/api/v1/reviews/",
        json={"appointment_id": appointment.id, "rating": 5.0},
        headers={"Authorization": f"Bearer {auth_context['token']}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_duplicate_review(client, auth_context, test_review):
    """Test that duplicate reviews are rejected."""
    response = await client.post(
        "/api/v1/reviews/",
        json={"appointment_id": test_review.appointment_id, "rating": 3.0},
        headers={"Authorization": f"Bearer {auth_context['token']}"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_review(client, auth_context, test_review):
    """Test updating a review."""
    response = await client.patch(
        f"/api/v1/reviews/{test_review.id}",
        json={"comment": "Обновленный комментарий", "is_published": False},
        headers={"Authorization": f"Bearer {auth_context['token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["comment"] == "Обновленный комментарий"
    assert data["is_published"] is False


@pytest.mark.asyncio
async def test_delete_review(client, auth_context, test_review):
    """Test deleting a review."""
    response = await client.delete(
        f"/api/v1/reviews/{test_review.id}",
        headers={"Authorization": f"Bearer {auth_context['token']}"},
    )
    assert response.status_code == 204

    # Verify review list no longer includes it
    response = await client.get("/api/v1/reviews/")
    assert response.status_code == 200
    data = response.json()
    assert all(r["id"] != test_review.id for r in data)
