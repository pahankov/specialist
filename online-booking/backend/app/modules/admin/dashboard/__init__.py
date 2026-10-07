"""Admin dashboard module — split from monolithic dashboard.py."""
from fastapi import APIRouter

from app.modules.admin.dashboard.overview import router as overview_router
from app.modules.admin.dashboard.reports import router as reports_router

# Aggregate all sub-routers
router = APIRouter()
router.include_router(overview_router)
router.include_router(reports_router)
