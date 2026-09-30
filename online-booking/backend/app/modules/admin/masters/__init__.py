"""Master management module — split from monolithic masters.py."""
from fastapi import APIRouter

from app.modules.admin.masters.crud import router as crud_router
from app.modules.admin.masters.status import router as status_router
from app.modules.admin.masters.stats import router as stats_router
from app.modules.admin.masters.bulk import router as bulk_router
from app.modules.admin.masters.import_csv import router as import_router
from app.modules.admin.masters.audit import router as audit_router

# Aggregate all sub-routers
router = APIRouter()
router.include_router(crud_router)
router.include_router(status_router)
router.include_router(stats_router)
router.include_router(bulk_router)
router.include_router(import_router)
router.include_router(audit_router)
