"""Admin appointments module — split from monolithic appointments.py."""
from fastapi import APIRouter

from app.modules.admin.appointments.actions import router as actions_router
from app.modules.admin.appointments.listing import router as listing_router
from app.modules.admin.appointments.booking import router as booking_router

# Aggregate all sub-routers (order mirrors the original file:
# specific action routes first, then listing, then booking)
router = APIRouter()
router.include_router(actions_router)
router.include_router(listing_router)
router.include_router(booking_router)
