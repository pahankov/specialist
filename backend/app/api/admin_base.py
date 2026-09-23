"""Shared imports for admin sub-routers."""
from fastapi import HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta, time
import csv
import io
from app.database import get_db
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.models.master import Master
from app.models.working_hour import WorkingHour
from app.models.blocked_slot import BlockedSlot
from app.models.audit_log import AuditLog
from app.schemas.appointment import AppointmentResponse, AppointmentCreate, AppointmentWithDetails, AdminBookingCreate
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.schemas.working_hour import WorkingHourCreate, WorkingHourUpdate, WorkingHourResponse
from app.schemas.audit_log import AuditLogResponse, AuditLogListResponse
from app.schemas.blocked_slot import BlockedSlotCreate, BlockedSlotResponse
from app.api.dependencies import require_master
from app.api.admin_helpers import get_owned_or_404, get_or_404
from app.api.audit_helper import log_action
