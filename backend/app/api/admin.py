"""Admin API router aggregator.

All admin endpoints are split into separate modules:
- admin_dashboard.py  — dashboard, monthly stats
- admin_appointments.py — appointment CRUD, booking, by-date
- admin_services.py   — service CRUD
- admin_clients.py    — client CRUD
- admin_working_hours.py — working hours CRUD
- admin_audit.py      — audit logs
- admin_export.py     — CSV exports
- admin_blocked_slots.py — blocked slots
"""
from fastapi import APIRouter
from app.api.admin_dashboard import router as dashboard_router
from app.api.admin_appointments import router as appointments_router
from app.api.admin_services import router as services_router
from app.api.admin_clients import router as clients_router
from app.api.admin_working_hours import router as working_hours_router
from app.api.admin_audit import router as audit_router
from app.api.admin_export import router as export_router
from app.api.admin_blocked_slots import router as blocked_slots_router

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

router.include_router(dashboard_router)
router.include_router(appointments_router)
router.include_router(services_router)
router.include_router(clients_router)
router.include_router(working_hours_router)
router.include_router(audit_router)
router.include_router(export_router)
router.include_router(blocked_slots_router)
