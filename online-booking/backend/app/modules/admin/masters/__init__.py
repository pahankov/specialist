"""Master management module — split from monolithic masters.py."""
from fastapi import APIRouter

from app.modules.admin.masters.status import router as status_router
from app.modules.admin.masters.stats import router as stats_router
from app.modules.admin.masters.import_csv import router as import_router
from app.modules.admin.masters.audit import router as audit_router
from app.modules.admin.masters.crud import router as crud_router

# Aggregate all sub-routers (bulk moved to admin router)
# IMPORTANT: Specific routes MUST come before generic /{master_id} routes
router = APIRouter()
router.include_router(import_router)  # /import must come before /{master_id}
router.include_router(audit_router)   # /audit must come before /{master_id}
router.include_router(stats_router)   # /{master_id}/stats must come before /{master_id}
router.include_router(status_router)  # /{master_id}/toggle-active must come before /{master_id}
router.include_router(crud_router)    # /{master_id} must be LAST
