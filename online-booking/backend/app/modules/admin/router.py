"""Admin API router aggregator."""
from fastapi import APIRouter
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

from app.modules.admin.dashboard import router as dashboard_router
from app.modules.admin.appointments import router as appointments_router
from app.modules.admin.services import router as services_router
from app.modules.admin.clients import router as clients_router
from app.modules.admin.working_hours import router as working_hours_router
from app.modules.admin.audit import router as audit_router
from app.modules.admin.export import router as export_router
from app.modules.admin.blocked_slots import router as blocked_slots_router
from app.modules.admin.masters import router as masters_router
from app.modules.admin.admin_reviews import router as admin_reviews_router
from app.modules.admin.health import router as health_router
from app.modules.admin.changelog import router as changelog_router

router.include_router(dashboard_router)
router.include_router(appointments_router)
router.include_router(services_router)
router.include_router(clients_router)
router.include_router(working_hours_router)
router.include_router(blocked_slots_router)
router.include_router(masters_router)
router.include_router(admin_reviews_router)
router.include_router(audit_router)
router.include_router(export_router)
router.include_router(health_router)
router.include_router(changelog_router)
